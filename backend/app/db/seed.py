"""Optional, idempotent dev seed: one demo user.

Run with:  python -m app.db.seed
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.models import User

logger = get_logger(__name__)

DEMO_EMAIL = "demo@medexplain.local"
DEMO_PASSWORD = "demo-password-123"  # noqa: S105  (dev-only seed credential)


def seed_demo(db: Session | None = None) -> None:
    owns_session = db is None
    db = db or SessionLocal()
    try:
        if db.query(User).filter(User.email == DEMO_EMAIL).first():
            logger.info("Seed: demo user already present (%s)", DEMO_EMAIL)
            return
        db.add(
            User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                full_name="Demo User",
            )
        )
        db.commit()
        logger.info("Seed: created demo user %s", DEMO_EMAIL)
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    configure_logging()
    from app.db import init_db

    init_db()
    seed_demo()
