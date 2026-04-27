# HW19 Verification Log

Date (UTC): 2026-04-27

EC2 Public IP: `13.223.42.205`

## Health Check
`curl -i http://13.223.42.205/api/v1/health`

```http
HTTP/1.1 200 OK
{"status":"healthy","service":"project-genesis-api"}
```

## DB Connectivity Check
`curl -i http://13.223.42.205/api/v1/db-check`

```http
HTTP/1.1 200 OK
{"db_status" : "connected", "database" : "genesisdb", "db_user" : "genesis", "server_time" : "2026-04-27T15:05:16.850273+00:00"}
```

Result: Project Genesis API loads via EC2 Public IP and successfully talks to RDS.
