import os
import threading
import time
from datetime import datetime, timezone

import psycopg2
import requests
from flask import Flask, jsonify, redirect, render_template_string, request, url_for
from psycopg2.extras import RealDictCursor


# Env/bootstrap: load local .env values once before app config.
def load_env_file(path=".env"):
    # Parse KEY=VALUE pairs from .env and set only missing OS env vars.
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()


# App config: Flask app + runtime settings.
app = Flask(__name__)
APP_ENV = os.getenv("APP_ENV")
API_KEY = os.getenv("API_KEY")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/cryptopulse",
)
AUTO_SAVE_INTERVAL_SECONDS = int(os.getenv("AUTO_SAVE_INTERVAL_SECONDS", "300"))
AUTO_SAVE_SOURCE = "auto"

# Guard values used by the autosave thread startup logic.
_auto_writer_started = False
_auto_writer_lock = threading.Lock()


# Database: connection and schema helpers for PostgreSQL.
def get_db_connection():
    # Open DB connection and use dict-like rows for easier serialization.
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    # Create table once; retry briefly to tolerate DB startup race.
    retries = 10
    for attempt in range(1, retries + 1):
        try:
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS crypto_results (
                            id SERIAL PRIMARY KEY,
                            bitcoin_usd DOUBLE PRECISION NOT NULL,
                            ethereum_usd DOUBLE PRECISION NOT NULL,
                            litecoin_usd DOUBLE PRECISION NOT NULL,
                            average_usd DOUBLE PRECISION NOT NULL,
                            spread_usd DOUBLE PRECISION NOT NULL,
                            highest VARCHAR(20) NOT NULL,
                            source VARCHAR(50) NOT NULL DEFAULT 'manual',
                            created_at TIMESTAMPTZ NOT NULL
                        )
                        """
                    )
                conn.commit()
                return
            finally:
                conn.close()
        except psycopg2.OperationalError as exc:
            if attempt == retries:
                raise
            app.logger.warning(
                "Database not ready yet (attempt %s/%s): %s",
                attempt,
                retries,
                exc,
            )
            time.sleep(2)


def build_metrics(btc_usd, eth_usd, ltc_usd):
    # Compute derived values returned by both live and stored-data endpoints.
    spread = round(btc_usd - eth_usd, 2)
    avg_price = round((btc_usd + eth_usd + ltc_usd) / 3, 2)
    price_map = {"bitcoin": btc_usd, "ethereum": eth_usd, "litecoin": ltc_usd}
    max_coin = max(price_map, key=price_map.get)
    return {"spread_usd": spread, "average_usd": avg_price, "highest": max_coin}


def row_to_result(row):
    # Normalize DB row shape into API-friendly JSON.
    created_at = row["created_at"]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()

    return {
        "id": row["id"],
        "prices": {
            "bitcoin_usd": row["bitcoin_usd"],
            "ethereum_usd": row["ethereum_usd"],
            "litecoin_usd": row["litecoin_usd"],
        },
        "spread_usd": row["spread_usd"],
        "average_usd": row["average_usd"],
        "highest": row["highest"],
        "source": row["source"],
        "created_at": row["created_at"],
    }


# External data + persistence helpers:
# fetch CoinGecko prices and persist normalized snapshots.
def fetch_crypto_prices():
    # Pull current BTC/ETH/LTC prices from CoinGecko and validate response.
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin,ethereum,litecoin", "vs_currencies": "usd"}
    resp = requests.get(
        url,
        params=params,
        headers={"Accept": "application/json", "User-Agent": "crypto-pulse/1.0"},
        timeout=10,
    )
    if resp.status_code != 200:
        raise ValueError(f"Upstream API returned status {resp.status_code}")

    data = resp.json()
    btc_usd = data.get("bitcoin", {}).get("usd")
    eth_usd = data.get("ethereum", {}).get("usd")
    ltc_usd = data.get("litecoin", {}).get("usd")
    if btc_usd is None or eth_usd is None or ltc_usd is None:
        raise ValueError("Public API response did not include expected fields.")

    return float(btc_usd), float(eth_usd), float(ltc_usd)


def save_crypto_snapshot(btc_usd, eth_usd, ltc_usd, source="manual"):
    # Save one snapshot row and return payload metadata for API responses.
    metrics = build_metrics(btc_usd, eth_usd, ltc_usd)
    source = str(source or "manual")[:50]
    created_at = datetime.now(timezone.utc)

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO crypto_results (
                    bitcoin_usd,
                    ethereum_usd,
                    litecoin_usd,
                    average_usd,
                    spread_usd,
                    highest,
                    source,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    btc_usd,
                    eth_usd,
                    ltc_usd,
                    metrics["average_usd"],
                    metrics["spread_usd"],
                    metrics["highest"],
                    source,
                    created_at,
                ),
            )
            inserted = cursor.fetchone()
        conn.commit()
    finally:
        conn.close()

    return {
        "id": inserted["id"],
        "metrics": metrics,
        "source": source,
        "created_at": inserted["created_at"].isoformat(),
    }


# Background autosave worker:
# runs in a daemon thread and writes one snapshot each interval.
def auto_save_crypto_loop():
    while True:
        try:
            btc_usd, eth_usd, ltc_usd = fetch_crypto_prices()
            save_crypto_snapshot(btc_usd, eth_usd, ltc_usd, source=AUTO_SAVE_SOURCE)
        except (requests.RequestException, ValueError, psycopg2.Error) as exc:
            app.logger.warning("Auto-save cycle failed: %s", exc)
        time.sleep(AUTO_SAVE_INTERVAL_SECONDS)


def ensure_auto_writer_started():
    # Start exactly one daemon writer thread per process.
    global _auto_writer_started
    if _auto_writer_started:
        return
    with _auto_writer_lock:
        if _auto_writer_started:
            return
        thread = threading.Thread(
            target=auto_save_crypto_loop,
            name="crypto-auto-writer",
            daemon=True,
        )
        thread.start()
        _auto_writer_started = True


init_db()


# Startup hooks: start background worker once per process.
if hasattr(app, "before_serving"):
    @app.before_serving
    def start_background_jobs():
        ensure_auto_writer_started()
else:
    @app.before_request
    def start_background_jobs():
        # Backward-compatible startup hook when before_serving is unavailable.
        ensure_auto_writer_started()


# Routes: UI, healthcheck, live crypto data, and snapshot CRUD.
@app.get("/")
def home():
    # Redirect root URL to dashboard for convenience.
    return redirect(url_for("index"))


@app.get("/api/v1/dashboard")
def index():
    # Serve lightweight dashboard UI as inline HTML.
    return render_template_string(
        """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Crypto Pulse</title>
    <style>
      @import url("https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600&family=Unbounded:wght@500;700&display=swap");
      :root {
        --bg: #f7f2ed;
        --ink: #1b1b1b;
        --muted: #5f5a53;
        --card: #ffffff;
        --accent: #ff8a3d;
        --accent-2: #ffe2cf;
        --accent-3: #2d6cdf;
        --shadow: 0 28px 80px -40px rgba(23, 23, 23, 0.5);
        --radius: 24px;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Space Grotesk", "Segoe UI", Arial, sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top right, #ffe8d0 0%, transparent 48%),
          radial-gradient(circle at 20% 20%, #e6f0ff 0%, transparent 52%),
          radial-gradient(circle at 80% 80%, #ffe9f2 0%, transparent 45%),
          var(--bg);
        min-height: 100vh;
      }
      main {
        max-width: 980px;
        margin: 0 auto;
        padding: 64px 24px 80px;
      }
      header {
        display: grid;
        gap: 16px;
        margin-bottom: 32px;
      }
      .eyebrow {
        text-transform: uppercase;
        letter-spacing: 0.22em;
        font-size: 12px;
        color: var(--muted);
      }
      h1 {
        margin: 0;
        font-family: "Unbounded", "Space Grotesk", sans-serif;
        font-size: clamp(34px, 5vw, 56px);
        line-height: 1.05;
      }
      p.lead {
        margin: 0;
        max-width: 560px;
        color: var(--muted);
        font-size: 16px;
      }
      .grid {
        display: grid;
        gap: 20px;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }
      .card {
        background: var(--card);
        border-radius: var(--radius);
        padding: 20px;
        box-shadow: var(--shadow);
        display: grid;
        gap: 10px;
        min-height: 160px;
        position: relative;
        overflow: hidden;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
      }
      .card::after {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(120deg, transparent 40%, var(--accent-2) 100%);
        opacity: 0.6;
        pointer-events: none;
      }
      .card:hover {
        transform: translateY(-4px);
        box-shadow: 0 36px 90px -45px rgba(23, 23, 23, 0.55);
      }
      .card h2 {
        margin: 0;
        font-size: 18px;
        position: relative;
        z-index: 1;
      }
      .metric {
        font-size: 30px;
        font-weight: 600;
        position: relative;
        z-index: 1;
      }
      .muted {
        color: var(--muted);
        font-size: 13px;
        position: relative;
        z-index: 1;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border-radius: 999px;
        background: var(--accent-2);
        color: #8a3a08;
        font-size: 12px;
        font-weight: 600;
        width: fit-content;
        position: relative;
        z-index: 1;
      }
      .pill {
        background: #1f1f1f;
        color: #fff;
        padding: 10px 14px;
        border-radius: 999px;
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      .row {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        align-items: center;
        justify-content: space-between;
      }
      .footer {
        margin-top: 24px;
        color: var(--muted);
        font-size: 13px;
      }
      .error {
        color: #b42318;
        background: #fff1f1;
        padding: 10px 14px;
        border-radius: 12px;
      }
      .hidden {
        display: none;
      }
      .skeleton {
        position: relative;
        overflow: hidden;
      }
      .skeleton::before {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(
          110deg,
          rgba(255, 255, 255, 0) 0%,
          rgba(255, 255, 255, 0.6) 50%,
          rgba(255, 255, 255, 0) 100%
        );
        transform: translateX(-100%);
        animation: shimmer 1.8s infinite;
      }
      @keyframes shimmer {
        100% {
          transform: translateX(100%);
        }
      }
    </style>
  </head>
  <body>
    <main>
      <header>
        <div class="eyebrow">Live data</div>
        <h1>Crypto Pulse Dashboard</h1>
        <p class="lead">
          A clean snapshot of upstream crypto prices with a few calculated insights.
        </p>
        <div class="row">
          <span class="pill">Source: CoinGecko</span>
          <span id="health" class="badge">Checking health...</span>
        </div>
      </header>

      <section class="grid" id="cards">
        <div class="card skeleton">
          <h2>Bitcoin</h2>
          <div class="metric" id="btc">$--</div>
          <div class="muted">USD price</div>
        </div>
        <div class="card skeleton">
          <h2>Ethereum</h2>
          <div class="metric" id="eth">$--</div>
          <div class="muted">USD price</div>
        </div>
        <div class="card skeleton">
          <h2>Litecoin</h2>
          <div class="metric" id="ltc">$--</div>
          <div class="muted">USD price</div>
        </div>
        <div class="card skeleton">
          <h2>Average</h2>
          <div class="metric" id="avg">$--</div>
          <div class="muted">Across three coins</div>
        </div>
        <div class="card skeleton">
          <h2>Spread</h2>
          <div class="metric" id="spread">$--</div>
          <div class="muted">BTC minus ETH</div>
        </div>
        <div class="card skeleton">
          <h2>Top Performer</h2>
          <div class="metric" id="highest">--</div>
          <div class="muted">Highest USD price</div>
        </div>
      </section>

      <div class="footer" id="status">Last updated: --</div>
      <div class="footer" id="error"></div>
    </main>

    <script>
      const formatUsd = (value) =>
        new Intl.NumberFormat("en-US", {
          style: "currency",
          currency: "USD",
          maximumFractionDigits: 2,
        }).format(value);

      async function loadHealth() {
        const badge = document.getElementById("health");
        try {
          const res = await fetch("/api/v1/health");
          const data = await res.json();
          if (res.ok) {
            badge.textContent = `Healthy - v${data.version}`;
          } else {
            badge.textContent = "Health check failed";
          }
        } catch (err) {
          badge.textContent = "Health check failed";
        }
      }

      async function loadData() {
        const cards = document.getElementById("cards");
        const cardList = cards.querySelectorAll(".card");
        const errorEl = document.getElementById("error");
        errorEl.textContent = "";
        errorEl.className = "footer";
        cardList.forEach((card) => card.classList.add("skeleton"));
        try {
          const res = await fetch("/api/v1/crypto");
          const data = await res.json();
          if (!res.ok) {
            throw new Error(data.message || "Upstream error");
          }

          document.getElementById("btc").textContent = formatUsd(
            data.prices.bitcoin_usd
          );
          document.getElementById("eth").textContent = formatUsd(
            data.prices.ethereum_usd
          );
          document.getElementById("ltc").textContent = formatUsd(
            data.prices.litecoin_usd
          );
          document.getElementById("avg").textContent = formatUsd(
            data.average_usd
          );
          document.getElementById("spread").textContent = formatUsd(
            data.spread_usd
          );
          document.getElementById("highest").textContent = data.highest
            .replace(/^\\w/, (c) => c.toUpperCase());

          document.getElementById("status").textContent =
            "Last updated: " + new Date().toLocaleTimeString();
          cards.classList.remove("hidden");
          cardList.forEach((card) => card.classList.remove("skeleton"));
        } catch (err) {
          cards.classList.add("hidden");
          errorEl.textContent =
            err && err.message
              ? "Failed to load data: " + err.message
              : "Failed to load data. Please try again later.";
          errorEl.className = "error";
        }
      }

      loadHealth();
      loadData();
      setInterval(loadData, 30000);
    </script>
  </body>
</html>
        """
    )


@app.get("/api/v1/health")
def health():
    # Lightweight probe endpoint for container/platform checks.
    return jsonify(status="healthy", version="1.0.0")


@app.get("/api/v1/crypto")
def crypto():
    # Return current upstream prices with calculated metrics.
    try:
        btc_usd, eth_usd, ltc_usd = fetch_crypto_prices()
    except requests.RequestException:
        return (
            jsonify(
                error="Upstream API request failed",
                message="Please try again later.",
            ),
            502,
        )

    except ValueError:
        return (
            jsonify(
                error="Invalid upstream data",
                message="Public API response did not include expected fields.",
            ),
            502,
        )

    metrics = build_metrics(btc_usd, eth_usd, ltc_usd)

    return jsonify(
        prices={
            "bitcoin_usd": btc_usd,
            "ethereum_usd": eth_usd,
            "litecoin_usd": ltc_usd,
        },
        spread_usd=metrics["spread_usd"],
        average_usd=metrics["average_usd"],
        highest=metrics["highest"],
    )


@app.post("/api/v1/crypto/results")
def create_crypto_result():
    # Validate user payload and save a manual snapshot row.
    payload = request.get_json(silent=True) or {}
    # Require three coin prices before attempting DB insert.
    required_fields = ["bitcoin_usd", "ethereum_usd", "litecoin_usd"]
    missing = [field for field in required_fields if field not in payload]
    if missing:
        return (
            jsonify(
                error="Invalid payload",
                message=f"Missing required fields: {', '.join(missing)}",
            ),
            400,
        )

    try:
        # Enforce numeric input to keep DB and metrics consistent.
        btc_usd = float(payload["bitcoin_usd"])
        eth_usd = float(payload["ethereum_usd"])
        ltc_usd = float(payload["litecoin_usd"])
    except (TypeError, ValueError):
        return (
            jsonify(
                error="Invalid payload",
                message="bitcoin_usd, ethereum_usd, and litecoin_usd must be numbers.",
            ),
            400,
        )

    saved = save_crypto_snapshot(
        btc_usd,
        eth_usd,
        ltc_usd,
        source=payload.get("source", "manual"),
    )

    return (
        jsonify(
            id=saved["id"],
            prices={
                "bitcoin_usd": btc_usd,
                "ethereum_usd": eth_usd,
                "litecoin_usd": ltc_usd,
            },
            spread_usd=saved["metrics"]["spread_usd"],
            average_usd=saved["metrics"]["average_usd"],
            highest=saved["metrics"]["highest"],
            source=saved["source"],
            created_at=saved["created_at"],
        ),
        201,
    )


@app.get("/api/v1/crypto/results")
def list_crypto_results():
    # Return latest rows, sorted by newest first.
    raw_limit = request.args.get("limit", "20")
    try:
        # Keep API safe from huge limits while supporting simple pagination.
        limit = max(1, min(int(raw_limit), 100))
    except ValueError:
        return (
            jsonify(error="Invalid query", message="limit must be an integer."),
            400,
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    bitcoin_usd,
                    ethereum_usd,
                    litecoin_usd,
                    average_usd,
                    spread_usd,
                    highest,
                    source,
                    created_at
                FROM crypto_results
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
    finally:
        conn.close()

    results = [row_to_result(row) for row in rows]
    return jsonify(count=len(results), items=results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
