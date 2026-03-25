# CryptoPulse

Lightweight Flask API that fetches data from CoinGecko and stores crypto snapshots in SQLite every five minutes.

![UI Dashboard](Screenshots/UI%20Dashboard.jpg)


## Quick Start (Docker Compose)

1. Start in detach mode:

```shell
docker compose up --build -d
```

2. Check app:

- http://127.0.0.1:5000/api/v1/health //output JSON
- http://127.0.0.1:5000/api/v1/crypto //output JSON
- http://127.0.0.1:5000/api/v1/dashboard

3. Stop app:

```shell
docker compose down
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

## Docker Optimization

`docker history cryptopulse:optimized` output after restructuring layers:

```text
IMAGE          CREATED          CREATED BY                                      SIZE      COMMENT
cd44e30cffa5   17 seconds ago   /bin/sh -c #(nop)  CMD ["python" "app.py"]      0B
6db2e3ff4b55   17 seconds ago   /bin/sh -c #(nop)  EXPOSE 5000                  0B
68a4287196a2   17 seconds ago   /bin/sh -c mkdir -p /app/data                   0B
3bf50d260706   18 seconds ago   /bin/sh -c #(nop) COPY dir:46c6ee8f7fb5f2233…   19.3MB
a9dfa1919e1a   21 seconds ago   /bin/sh -c pip install --no-cache-dir -r req…   7.7MB
40ddd9021481   31 seconds ago   /bin/sh -c #(nop) COPY file:f71d6f9255c1088b…   46B
9e7881e754d6   31 seconds ago   /bin/sh -c #(nop) WORKDIR /app                  0B
190b2ace1b35   31 seconds ago   /bin/sh -c #(nop)  ENV PYTHONUNBUFFERED=1       0B
a9c7f7b54f9c   32 seconds ago   /bin/sh -c #(nop)  ENV PYTHONDONTWRITEBYTECO…   0B
fb1118f126b5   8 days ago       CMD ["python3"]                                 0B        buildkit.dockerfile.v0
<missing>      8 days ago       RUN /bin/sh -c set -eux;  for src in idle3 p…   36B       buildkit.dockerfile.v0
<missing>      8 days ago       RUN /bin/sh -c set -eux;   savedAptMark="$(a…   36.8MB    buildkit.dockerfile.v0
<missing>      8 days ago       ENV PYTHON_SHA256=c08bc65a81971c1dd578318282…   0B        buildkit.dockerfile.v0
<missing>      8 days ago       ENV PYTHON_VERSION=3.12.13                      0B        buildkit.dockerfile.v0
<missing>      8 days ago       ENV GPG_KEY=7169605F62C751356D054A26A821E680…   0B        buildkit.dockerfile.v0
<missing>      8 days ago       RUN /bin/sh -c set -eux;  apt-get update;  a…   3.81MB    buildkit.dockerfile.v0
<missing>      8 days ago       ENV LANG=C.UTF-8                                0B        buildkit.dockerfile.v0
<missing>      8 days ago       ENV PATH=/usr/local/bin:/usr/local/sbin:/usr…   0B        buildkit.dockerfile.v0
<missing>      9 days ago       # debian.sh --arch 'amd64' out/ 'trixie' '@1…   78.6MB    debuerreotype 0.17
```

Placing `COPY requirements.txt ./` before `COPY . .` lets Docker cache the dependency-install layer independently from application source changes. As a result, if you only change Python code but not dependencies, Docker reuses the cached `pip install` layer instead of reinstalling packages. This significantly reduces rebuild time during active development.
