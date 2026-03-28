# CryptoPulse

Flask API for crypto prices with PostgreSQL persistence, deployed as a 3-container Docker Compose stack behind Nginx.

![UI Dashboard](Screenshots/UI%20Dashboard.jpg)

## Architecture Summary

Compose stack has 3 containers:
- `nginx` - reverse proxy, exposed on host `http://localhost:8080`
- `crypto-api` - Flask API service (internal port `5000`)
- `postgres` - PostgreSQL database with persistent named volume `postgres_data`

Traffic flow:
1. User sends request to `localhost:8080`
2. Nginx proxies request to `crypto-api:5000`
3. API reads/writes data in PostgreSQL (`postgres:5432`)
4. DB data persists in Docker volume `postgres_data`

## Run Instructions

1. Clone repository and enter folder:

```bash
git clone <your-repo-url>
cd CryptoPulse
```

2. Build and start all services:

```bash
docker compose up --build -d
```

3. Check endpoints:

- `http://localhost:8080/api/v1/health`
- `http://localhost:8080/api/v1/crypto`
- `http://localhost:8080/api/v1/dashboard`

4. Stop and remove stack:

```bash
docker compose down
```

5. Stop and remove stack + DB volume (full reset):

```bash
docker compose down -v
```

## Database Endpoints

- `POST /api/v1/crypto/results` - write the current record manually
- `GET /api/v1/crypto/results?limit=20` - read the last 20 records

## Example CRUD Requests

Create row (manual mode):

```bash
curl -X POST http://127.0.0.1:8080/api/v1/crypto/results \
  -H "Content-Type: application/json" \
  -d "{\"bitcoin_usd\": 68950.10, \"ethereum_usd\": 3550.00, \"litecoin_usd\": 85.40, \"source\": \"manual-test\"}"
```

Read rows (limit 10 records):

```bash
curl "http://127.0.0.1:8080/api/v1/crypto/results?limit=10"
```
