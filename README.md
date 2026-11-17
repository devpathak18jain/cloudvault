# CloudVault: Cloud File Storage and Sharing

A small web app where users register, upload files, download them, and share them
through expiring links. Built to run the same way on a laptop and on AWS.

**Stack:** Python/Flask, SQLite, Gunicorn, Docker, Amazon EC2, Amazon S3, ECR, IAM,
Trivy, GitHub Actions. These are the same tools as in Cloud Computing Lab Report 2.

## Run it locally (no Docker)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q                          # 16 tests should pass
flask --app wsgi run               # open http://127.0.0.1:5000
```

## Run it with Docker
```bash
cp .env.example .env               # then set SECRET_KEY
docker compose up --build          # open http://localhost
```

## Features
- Register / login (hashed passwords, CSRF protection, secure session cookies)
- Upload with size limit, file-type allow-list, per-user quota
- Private downloads; only the owner can access, delete or share a file
- Share links that expire (1 hour to 30 days) and can be switched off
- `/health` endpoint for Docker and monitoring
- Storage switch: `STORAGE_BACKEND=local` (disk) or `s3` (Amazon S3, via the EC2 IAM role)

## Roadmap (step by step)
1. App built and tested locally (done)
2. Containerize and run with Docker (see STEP2_DOCKER.md for laptop, STEP2_EC2_DEPLOY.md for AWS)
3. Launch an EC2 instance and deploy with docker compose
4. Move files to S3 and use an IAM role with least privilege
5. CI/CD with GitHub Actions: tests, Semgrep, Trivy, push to ECR
6. Hardening (HTTPS, backups) and optional k3s deployment
7. Final report, PPT and viva Q&A

## Layout
```
cloudvault/   app package (routes, storage backends, templates)
tests/        pytest suite
wsgi.py       entry point for Gunicorn
Dockerfile, docker-compose.yml, .env.example
```
