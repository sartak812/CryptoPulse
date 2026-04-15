# AWS Deployment Proof (HW15)

## EC2 Info

- Provider: AWS EC2
- Region: `us-east-1`
- Instance type: `t3.micro`
- Instance ID: `i-0fc9471b00e14292f`
- Public IP: `98.91.234.229`

## 1) Cloud Terminal: `docker ps`

```text
NAMES                   IMAGE                    STATUS                   PORTS
crypto-pulse-nginx      nginx:1.27-alpine        Up 6 minutes             0.0.0.0:80->80/tcp, [::]:80->80/tcp
crypto-pulse-api        cryptopulse-crypto-api   Up 6 minutes             5000/tcp
crypto-pulse-postgres   postgres:16-alpine       Up 6 minutes (healthy)   5432/tcp
```

## 2) Backend API via Public IP

- URL: `http://98.91.234.229/api/v1/health`
- Response:

```json
{"status":"healthy","version":"1.0.0"}
```

## 3) Frontend via Public IP

- URL: `http://98.91.234.229/api/v1/dashboard`
- Submission note: `Updated for PR on 2026-04-15`

![Frontend Dashboard](Screenshots/UI%20Dashboard.jpg)

## Screenshot Embeds (add/replace with final browser+terminal captures)

Use these names for final submission files:

- `Screenshots/aws-docker-ps.png`
- `Screenshots/aws-backend-health.png`
- `Screenshots/aws-frontend-dashboard.png`

Then keep these embeds in this file:

![AWS Docker PS](Screenshots/aws-docker-ps.png)

![AWS Backend Health](Screenshots/aws-backend-health.png)

![AWS Frontend Dashboard](Screenshots/aws-frontend-dashboard.png)
