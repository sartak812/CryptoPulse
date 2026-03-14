## Import OS utilities to read and set environment variables.
import os
import sqlite3
# Import Path helper for safe file path operations.
from pathlib import Path
from datetime import datetime, timezone

# Import HTTP client library for upstream API requests.
import requests
# Import Flask primitives used by this application.
from flask import Flask, jsonify, redirect, render_template_string, request, url_for


# Define helper function that loads key/value pairs from a .env file.
def load_env_file(path=".env"):
    # Build a Path object from the provided file path.
    env_path = Path(path)
    # Stop early if the .env file does not exist.
    if not env_path.exists():
        # Return without doing anything when file is missing.
        return
    # Iterate over all lines in the .env file.
    for raw_line in env_path.read_text().splitlines():
        # Remove leading/trailing spaces for reliable parsing.
        line = raw_line.strip()
        # Skip empty lines, comments, and lines without key/value delimiter.
        if not line or line.startswith("#") or "=" not in line:
            # Continue to the next line when current line is not usable.
            continue
        # Split line into key and value only on the first "=" symbol.
        key, value = line.split("=", 1)
        # Trim spaces from environment variable key.
        key = key.strip()
        # Trim spaces and optional quotes from environment variable value.
        value = value.strip().strip('"').strip("'")
        # Set variable only if it is not already present in the environment.
        os.environ.setdefault(key, value)


# Load environment variables from local .env file at startup.
load_env_file()


# Create Flask application instance.
app = Flask(__name__)
# Read APP_ENV variable for potential environment-specific behavior.
APP_ENV = os.getenv("APP_ENV")
# Read API_KEY variable for potential authenticated upstream calls.
API_KEY = os.getenv("API_KEY")
# Read database path from environment for flexible local/docker setup.
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/crypto.db")


# Define helper that opens a new SQLite connection per request or action.
def get_db_connection():
    # Create parent directory for DB file when it does not exist yet.
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    # Open sqlite database file configured by DATABASE_PATH.
    conn = sqlite3.connect(DATABASE_PATH)
    # Allow dictionary-style column access (row["column_name"]).
    conn.row_factory = sqlite3.Row
    # Return open connection to caller.
    return conn


# Define one-time DB bootstrap that creates required table.
def init_db():
    # Open connection for schema initialization.
    conn = get_db_connection()
    # Wrap writes in try/finally so connection always closes.
    try:
        # Create table for saved crypto snapshots if it does not exist.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crypto_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bitcoin_usd REAL NOT NULL,
                ethereum_usd REAL NOT NULL,
                litecoin_usd REAL NOT NULL,
                average_usd REAL NOT NULL,
                spread_usd REAL NOT NULL,
                highest TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL
            )
            """
        )
        # Persist schema creation to disk.
        conn.commit()
    finally:
        # Close connection regardless of success or failure.
        conn.close()


# Define helper that computes derived metrics from 3 coin prices.
def build_metrics(btc_usd, eth_usd, ltc_usd):
    # Compute BTC minus ETH spread rounded to two decimals.
    spread = round(btc_usd - eth_usd, 2)
    # Compute average price across selected coins rounded to two decimals.
    avg_price = round((btc_usd + eth_usd + ltc_usd) / 3, 2)
    # Build temporary map coin->price to detect highest coin.
    price_map = {"bitcoin": btc_usd, "ethereum": eth_usd, "litecoin": ltc_usd}
    # Pick coin name that has the highest USD value.
    max_coin = max(price_map, key=price_map.get)
    # Return all computed values in one dictionary.
    return {"spread_usd": spread, "average_usd": avg_price, "highest": max_coin}


# Define helper that normalizes a DB row into API JSON structure.
def row_to_result(row):
    # Return plain dict that can be serialized by jsonify.
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


# Initialize the sqlite schema at startup so routes can use DB immediately.
init_db()


# Register route for root URL.
@app.get("/")
# Define handler that redirects users to the dashboard endpoint.
def home():
    # Redirect to function named "index" (route /api/v1/data).
    return redirect(url_for("index"))


# Register route for the dashboard page.
@app.get("/api/v1/data")
# Define handler that returns HTML UI.
def index():
    # Return inline HTML template as a Flask response.
    return render_template_string(
        # Keep full front-end template inline for a single-file demo app.
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


# Register route for health checks.
@app.get("/api/v1/health")
# Define lightweight endpoint to confirm service status.
def health():
    # Return service health and version in JSON format.
    return jsonify(status="healthy", version="1.0.0")


# Register route that fetches and aggregates crypto prices.
@app.get("/api/v1/crypto")
# Define endpoint that proxies CoinGecko data and computes metrics.
def crypto():
    # Define upstream CoinGecko simple price API URL.
    url = "https://api.coingecko.com/api/v3/simple/price"
    # Define request query parameters for required coins and currency.
    params = {"ids": "bitcoin,ethereum,litecoin", "vs_currencies": "usd"}
    # Begin protected request block to catch network-related failures.
    try:
        # Send GET request to upstream API with headers and timeout.
        resp = requests.get(
            # Pass upstream endpoint URL.
            url,
            # Pass query string parameters.
            params=params,
            # Pass explicit headers for clarity and API friendliness.
            headers={"Accept": "application/json", "User-Agent": "crypto-pulse/1.0"},
            # Fail request if upstream does not respond in 10 seconds.
            timeout=10,
        )
    # Catch connection, timeout, DNS, and other request exceptions.
    except requests.RequestException:
        # Return structured JSON error with bad gateway status.
        return (
            # Create error payload.
            jsonify(
                # Short error category.
                error="Upstream API request failed",
                # Human-readable message for UI clients.
                message="Please try again later.",
            ),
            # Mark failure as upstream dependency issue.
            502,
        )

    # Check if upstream response is not successful.
    if resp.status_code != 200:
        # Return structured error describing non-200 upstream status.
        return (
            # Create error payload.
            jsonify(
                # Short error category.
                error="Upstream API error",
                # Human-readable message for UI clients.
                message="Public API returned a non-200 status.",
                # Include upstream status code for debugging.
                status_code=resp.status_code,
            ),
            # Mark failure as upstream dependency issue.
            502,
        )

    # Parse upstream JSON body into Python dictionary.
    data = resp.json()
    # Extract Bitcoin price in USD.
    btc_usd = data.get("bitcoin", {}).get("usd")
    # Extract Ethereum price in USD.
    eth_usd = data.get("ethereum", {}).get("usd")
    # Extract Litecoin price in USD.
    ltc_usd = data.get("litecoin", {}).get("usd")
    # Validate that all required price fields are present.
    if btc_usd is None or eth_usd is None or ltc_usd is None:
        # Return error when expected fields are missing from upstream response.
        return (
            # Create error payload.
            jsonify(
                # Short error category.
                error="Invalid upstream data",
                # Human-readable message for UI clients.
                message="Public API response did not include expected fields.",
            ),
            # Mark failure as upstream dependency issue.
            502,
        )

    # Compute spread, average, and highest coin via shared helper.
    metrics = build_metrics(btc_usd, eth_usd, ltc_usd)

    # Return normalized JSON payload consumed by the front-end dashboard.
    return jsonify(
        # Include raw per-coin USD prices.
        prices={
            # Provide Bitcoin USD value.
            "bitcoin_usd": btc_usd,
            # Provide Ethereum USD value.
            "ethereum_usd": eth_usd,
            # Provide Litecoin USD value.
            "litecoin_usd": ltc_usd,
        },
        # Include computed spread metric.
        spread_usd=metrics["spread_usd"],
        # Include computed average metric.
        average_usd=metrics["average_usd"],
        # Include coin name with highest USD value.
        highest=metrics["highest"],
    )


# Register route that stores user-provided crypto prices in SQLite.
@app.post("/api/v1/crypto/results")
# Define endpoint that accepts JSON and persists one snapshot row.
def create_crypto_result():
    # Parse request body as JSON safely.
    payload = request.get_json(silent=True) or {}
    # Validate required fields one by one for clearer user errors.
    required_fields = ["bitcoin_usd", "ethereum_usd", "litecoin_usd"]
    missing = [field for field in required_fields if field not in payload]
    # Return 400 when required fields are missing from payload.
    if missing:
        return (
            jsonify(
                error="Invalid payload",
                message=f"Missing required fields: {', '.join(missing)}",
            ),
            400,
        )

    # Convert incoming values to float so DB always stores numeric data.
    try:
        btc_usd = float(payload["bitcoin_usd"])
        eth_usd = float(payload["ethereum_usd"])
        ltc_usd = float(payload["litecoin_usd"])
    except (TypeError, ValueError):
        # Reject non-numeric values to keep metrics consistent.
        return (
            jsonify(
                error="Invalid payload",
                message="bitcoin_usd, ethereum_usd, and litecoin_usd must be numbers.",
            ),
            400,
        )

    # Compute derived metrics from the provided three prices.
    metrics = build_metrics(btc_usd, eth_usd, ltc_usd)
    # Read optional source label from payload for traceability.
    source = str(payload.get("source", "manual"))[:50]
    # Create UTC timestamp string for DB row.
    created_at = datetime.now(timezone.utc).isoformat()

    # Open DB connection for INSERT operation.
    conn = get_db_connection()
    # Ensure connection closes even if SQL fails.
    try:
        # Insert one snapshot row and receive assigned id.
        cursor = conn.execute(
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        # Persist insert transaction.
        conn.commit()
        # Read generated row id from insert cursor.
        created_id = cursor.lastrowid
    finally:
        # Close DB connection.
        conn.close()

    # Return inserted row summary to client.
    return (
        jsonify(
            id=created_id,
            prices={
                "bitcoin_usd": btc_usd,
                "ethereum_usd": eth_usd,
                "litecoin_usd": ltc_usd,
            },
            spread_usd=metrics["spread_usd"],
            average_usd=metrics["average_usd"],
            highest=metrics["highest"],
            source=source,
            created_at=created_at,
        ),
        201,
    )


# Register route that returns previously saved crypto snapshots.
@app.get("/api/v1/crypto/results")
# Define endpoint that reads rows from sqlite and returns JSON list.
def list_crypto_results():
    # Read optional result limit from query params.
    raw_limit = request.args.get("limit", "20")
    # Validate and clamp the limit to avoid returning huge payloads.
    try:
        limit = max(1, min(int(raw_limit), 100))
    except ValueError:
        return (
            jsonify(error="Invalid query", message="limit must be an integer."),
            400,
        )

    # Open DB connection for SELECT operation.
    conn = get_db_connection()
    # Ensure connection closes after query.
    try:
        # Query latest rows first so newest snapshots appear on top.
        rows = conn.execute(
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
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        # Close DB connection.
        conn.close()

    # Convert sqlite rows into JSON-serializable dictionaries.
    results = [row_to_result(row) for row in rows]
    # Return list and count metadata.
    return jsonify(count=len(results), items=results)


# Check whether this module is being run directly.
if __name__ == "__main__":
    # Start Flask development server with debug mode enabled.
    app.run(debug=True)
