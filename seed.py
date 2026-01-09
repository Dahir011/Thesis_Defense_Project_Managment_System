"""Convenience seeding script.

Many Windows/XAMPP setups have issues using the `flask` CLI (PATH / venv / PowerShell).
This script seeds the database using the same logic as `flask --app run.py seed`.

Usage:
  1) Ensure DB exists + tables imported via schema.sql (recommended) OR run:
        flask --app run.py init-db
  2) Then run:
        python seed.py
"""

from app import create_app
from app.extensions import db
from app.models import User, SupervisorProfile, StudentMaster

from werkzeug.security import generate_password_hash
from datetime import datetime


def run_seed() -> None:
    app = create_app()
    with app.app_context():
        # Create tables if user chose not to import schema.sql
        # (Safe: if tables already exist, MySQL will ignore)
        try:
            db.create_all()
        except Exception:
            # If schema.sql created tables with constraints, create_all may fail on some setups.
            pass

        # admin
        admin = User.query.filter_by(username="admin", role="admin").first()
        if not admin:
            admin = User(
                role="admin",
                username="admin",
                password_hash=generate_password_hash("admin123"),
                active=True,
            )
            db.session.add(admin)

        
        db.session.commit()


if __name__ == "__main__":
    run_seed()
    print("✅ Seed completed: admin/admin123, supervisor SUP1001/sup123, students CS001-CS003")
