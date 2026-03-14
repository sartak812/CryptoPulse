![UI Dashboard](Screenshots/UI%20Dashboard.jpg)

# Crypto Pulse API

Crypto Pulse is a Flask backend that:
- fetches live crypto prices from CoinGecko,
- calculates custom metrics (average, spread, top performer),
- stores user-submitted crypto snapshots in a SQLite database,
- serves a simple dashboard UI.

## Features

- `GET /api/v1/health` for service health checks
- `GET /api/v1/crypto` for live upstream crypto metrics
- `POST /api/v1/crypto/results` to save crypto prices into SQLite
- `GET /api/v1/crypto/results` to read saved rows from SQLite
- `GET /api/v1/data` for browser dashboard

## Database Structure

The app uses SQLite and creates one table automatically on startup:

Table: `crypto_results`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `bitcoin_usd` REAL NOT NULL
- `ethereum_usd` REAL NOT NULL
- `litecoin_usd` REAL NOT NULL
- `average_usd` REAL NOT NULL
- `spread_usd` REAL NOT NULL
- `highest` TEXT NOT NULL
- `source` TEXT NOT NULL (default `manual`)
- `created_at` TEXT NOT NULL (UTC ISO timestamp)

The DB file path is controlled by the environment variable `DATABASE_PATH`.

## Local Setup (Windows PowerShell)

1. Create a virtual environment:

```powershell
python -m venv .venv
```

2. Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Optional: set DB path (default is `data/crypto.db`):

```powershell
$env:DATABASE_PATH="data/crypto.db"
```

5. Run app:

```powershell
python app.py
```

Server URL: `http://127.0.0.1:5000`  
Dashboard URL: `http://127.0.0.1:5000/api/v1/data`

## Docker Setup (SQLite in Container)

This project includes `Dockerfile` and `docker-compose.yml`.

1. Build and start:

```powershell
docker compose up --build
```

2. Open API:

- `http://127.0.0.1:5000/api/v1/health`
- `http://127.0.0.1:5000/api/v1/crypto/results`

SQLite file is stored in Docker volume `sqlite_data` mounted to `/app/data`, and inside container path is:

`/app/data/crypto.db`

## API Endpoints

- `GET /` -> redirects to `/api/v1/data`
- `GET /api/v1/health` -> returns service status and version
- `GET /api/v1/crypto` -> returns live prices and metrics
- `GET /api/v1/data` -> returns dashboard HTML page
- `POST /api/v1/crypto/results` -> saves a crypto snapshot to DB
- `GET /api/v1/crypto/results?limit=20` -> reads latest saved snapshots

## Example CRUD Requests

Create row:

```bash
curl -X POST http://127.0.0.1:5000/api/v1/crypto/results \
  -H "Content-Type: application/json" \
  -d "{\"bitcoin_usd\": 68950.10, \"ethereum_usd\": 3550.00, \"litecoin_usd\": 85.40, \"source\": \"manual-test\"}"
```

Read rows:

```bash
curl "http://127.0.0.1:5000/api/v1/crypto/results?limit=10"
```
