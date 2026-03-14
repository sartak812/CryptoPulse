## Application UI

![UI Dashboard](Screenshots/UI%20Dashboard.jpg)
![UI Error API](Screenshots/UI%20Error%20API.jpg)

# CryptoPulse

Lightweight Flask API that fetches data from CoinGecko and stores crypto snapshots in SQLite every five minutes.

## Quick Start (Docker Compose)

1. Start in detach mode:

```shell
docker compose up --build -d
```

2. Check app:

- http://127.0.0.1:5000/api/v1/health
- http://127.0.0.1:5000/api/v1/crypto
- http://127.0.0.1:5000/api/v1/dashboard

3. Stop app:

```shell
docker compose down -v 
```

## Database

SQLite file path in container: `/app/data/crypto.db`.
Table: `crypto_results`.

## Database Endpoints

- `POST /api/v1/crypto/results`  //write the current record manually 
- `GET /api/v1/crypto/results?limit=20` //read the last 20 records


## Example CRUD Requests

Create row: (manual mode)

```bash
curl -X POST http://127.0.0.1:5000/api/v1/crypto/results \
  -H "Content-Type: application/json" \
  -d "{\"bitcoin_usd\": 68950.10, \"ethereum_usd\": 3550.00, \"litecoin_usd\": 85.40, \"source\": \"manual-test\"}"
```

Read rows: (limit 10 records)

```bash
curl "http://127.0.0.1:5000/api/v1/crypto/results?limit=10"
```
