# PhishSim

PhishSim is a security-awareness and authorized phishing-simulation platform built with FastAPI and PostgreSQL.

## Repository

This repository contains the application source, database migrations, deployment scripts, and example configuration.

## Security

Use this platform only for authorized security-awareness exercises and controlled internal testing. Do not commit credentials, secrets, production `.env` files, private keys, or recipient data.

## RHEL 9

Deployment helpers are provided under `scripts/` for RHEL-family systems. Review and harden the environment before production use, including HTTPS, a dedicated service account, MFA, PostgreSQL access controls, and firewall policy.
