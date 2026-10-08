#!/usr/bin/env python3
"""PhishSim management CLI.

Usage:
    python manage.py create-admin --email admin@example.org --full-name "Jane Doe" [--role super_admin]
    python manage.py migrate
    python manage.py seed-demo
    python manage.py test-email --sender-profile-id <id> --to test@example.org
    python manage.py campaign-status [--campaign-id <id>]
    python manage.py emergency-stop --reason "..."
    python manage.py cleanup
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="manage.py", description="PhishSim management CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create_admin = sub.add_parser("create-admin", help="Create a new administrator account")
    p_create_admin.add_argument("--email", required=True)
    p_create_admin.add_argument("--full-name", required=True)
    p_create_admin.add_argument("--role", default="super_admin", choices=["super_admin", "security_administrator", "campaign_manager", "analyst", "read_only"])
    p_create_admin.add_argument("--password", default=None, help="If omitted, you will be prompted securely.")

    sub.add_parser("migrate", help="Apply database migrations (alembic upgrade head)")
    sub.add_parser("seed-demo", help="Load demo administrators, recipients, templates, and landing pages")

    p_test_email = sub.add_parser("test-email", help="Send a test email through a configured sender profile")
    p_test_email.add_argument("--sender-profile-id", required=True)
    p_test_email.add_argument("--to", required=True, dest="to_address")

    p_status = sub.add_parser("campaign-status", help="Show status/progress for campaigns")
    p_status.add_argument("--campaign-id", default=None)

    p_stop = sub.add_parser("emergency-stop", help="Engage the global emergency stop (pauses all running campaigns)")
    p_stop.add_argument("--reason", required=True)

    sub.add_parser("cleanup", help="Apply retention policy: purge campaign events past their campaign's retention window")

    args = parser.parse_args()

    if args.command == "migrate":
        sys.exit(subprocess.call(["alembic", "upgrade", "head"]))

    from app.cli import commands

    if args.command == "create-admin":
        commands.cmd_create_admin(args.email, args.full_name, args.role, args.password)
    elif args.command == "seed-demo":
        commands.cmd_seed_demo()
    elif args.command == "test-email":
        commands.cmd_test_email(args.sender_profile_id, args.to_address)
    elif args.command == "campaign-status":
        commands.cmd_campaign_status(args.campaign_id)
    elif args.command == "emergency-stop":
        commands.cmd_emergency_stop(args.reason)
    elif args.command == "cleanup":
        commands.cmd_cleanup()


if __name__ == "__main__":
    main()
