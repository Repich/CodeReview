from __future__ import annotations

import argparse
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
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Administrator")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        user = db.query(UserAccount).filter(UserAccount.email == args.email).first()
        if user:
            user.password_hash = hash_password(args.password)
            user.role = UserRole.ADMIN
            user.status = "active"
            user.name = args.name or user.name
        else:
            user = UserAccount(
                email=args.email,
                name=args.name,
                password_hash=hash_password(args.password),
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
