# HW30 Submission Evidence

## DockerHub image

- Repository: https://hub.docker.com/r/sartak812/genesis
- Latest tag: `sartak812/genesis:latest`
- Pull command:

```bash
docker pull sartak812/genesis:latest
```

## GitHub Actions

- Workflow: `Genesis CI/CD`
- Branch: `hw30`
- Successful run: https://github.com/sartak812/CryptoPulse/actions/runs/26847554833

## Security check

No credentials are hardcoded in `.github/workflows/ci.yml`.
DockerHub credentials are read from GitHub repository secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
