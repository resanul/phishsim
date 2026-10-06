# PhishSim

PhishSim is an authorized security-awareness and phishing-simulation platform built around FastAPI, PostgreSQL, database migrations, and RHEL-friendly deployment scripts.

> **Authorized use only.** Run simulations only against systems, domains, mailboxes, and recipients for which you have explicit permission.

## Repository layout

```text
backend/        FastAPI application, models, services, web routes, migrations
frontend/       Frontend/template assets included by the source package
scripts/        Bootstrap, server, and systemd deployment helpers
tests/          Automated tests
docker/         Container/deployment assets
.env.example    Safe configuration template
```

## Clone and run

```bash
git clone https://github.com/resanul/phishsim.git
cd phishsim
cp .env.example .env
./scripts/bootstrap.sh --no-serve
./scripts/run_server.sh
```

The default development bind is `0.0.0.0:9988`; review `.env` and firewall policy before exposing it beyond a trusted network.

## Update after a Git push

```bash
git pull --ff-only
./scripts/bootstrap.sh --no-serve
sudo systemctl restart phishsim
```

## Security hygiene

- Never commit `.env`, credentials, private keys, tokens, or real recipient datasets.
- Keep `.env.example` free of real secrets.
- Use this project only for controlled, authorized awareness exercises.
