# Step 2: Containerize CloudVault with Docker

**Goal:** package the app into a Docker image and run it as a container, so it behaves the same on your laptop and on EC2.

## Why Docker here
The image holds Python, Flask, Gunicorn and the app code. Anyone with Docker can run it with one command, which is exactly what we do on EC2 in Step 3.

## What the Dockerfile does (explain this in your viva)
| Line | Purpose |
|---|---|
| `FROM python:3.12-slim` | small base image, fewer vulnerabilities for Trivy to find |
| `COPY requirements.txt` then `pip install` | dependencies are copied first so Docker caches this layer |
| `COPY cloudvault ./cloudvault` | app code is copied last, so code changes rebuild fast |
| `useradd appuser` + `USER appuser` | the app does not run as root |
| `VOLUME /data` | database and uploads live outside the image, so they survive restarts |
| `HEALTHCHECK` | Docker calls `/health` every 30 s and marks the container healthy or unhealthy |
| `CMD gunicorn ...` | production web server instead of Flask's development server |

## Run it
```bash
cp .env.example .env
python3 -c "import secrets;print(secrets.token_hex(32))"   # paste the output as SECRET_KEY in .env
docker compose up --build -d
docker compose ps                  # STATUS should become "healthy"
scripts/smoke_test.sh http://localhost
```
Open http://localhost and register an account.

## Prove the data is persistent
```bash
docker compose down                # removes the container, keeps the volume
docker compose up -d               # your account and files are still there
docker compose down -v             # -v also deletes the volume (data is gone)
```

## Useful commands
```bash
docker compose logs -f             # live logs
docker exec -it cloudvault-cloudvault-1 whoami   # prints appuser, not root
docker images cloudvault           # image size
```

## Troubleshooting
- **Port 80 already in use:** change `"80:8000"` to `"8080:8000"` in docker-compose.yml, then use http://localhost:8080
- **Permission denied on Linux:** run `sudo usermod -aG docker $USER`, then log out and in
- **Status stays "starting":** run `docker compose logs`; a missing `.env` file is the usual cause

## Screenshots to take for your report
1. `docker compose ps` showing healthy
2. smoke test output with all PASS
3. the dashboard in the browser
4. `docker exec ... whoami` showing appuser
