from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from backend.app.core.security import hash_password
from backend.app.db.session import SessionLocal
from backend.app.models.enums import UserRole
from backend.app.models.user import UserAccount


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update an admin user.")
    parser.add_argument("--email", required=True)
    password_group = parser.add_mutually_exclusive_group()
    password_group.add_argument(
        "--password-env",
        help="Read the password from this environment variable (preferred for automation).",
    )
    password_group.add_argument(
        "--password",
        help="Deprecated: visible in shell history and process listings.",
    )
    parser.add_argument("--name", default="Administrator")
    return parser.parse_args()


def resolve_password(args: argparse.Namespace) -> str:
    if args.password_env:
        password = os.getenv(args.password_env, "")
        if not password:
            raise ValueError(f"Environment variable {args.password_env!r} is empty")
        return password
    if args.password:
        return args.password
    password = getpass.getpass("Admin password: ")
    confirmation = getpass.getpass("Repeat admin password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match")
    if not password:
        raise ValueError("Password must be non-empty")
    return password


def main() -> int:
    args = parse_args()
    password = resolve_password(args)
    db = SessionLocal()
    try:
        user = db.query(UserAccount).filter(UserAccount.email == args.email).first()
        if user:
            user.password_hash = hash_password(password)
            user.role = UserRole.ADMIN
            user.status = "active"
            user.name = args.name or user.name
        else:
            user = UserAccount(
                email=args.email,
                name=args.name,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
            )
            db.add(user)
        db.commit()
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
