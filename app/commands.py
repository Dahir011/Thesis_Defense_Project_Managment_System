import click
from werkzeug.security import generate_password_hash
from datetime import datetime

from .extensions import db
from .models import User, SupervisorProfile, StudentMaster

def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        """Create all tables (development). For XAMPP/MySQL you can also use schema.sql."""
        with app.app_context():
            db.create_all()
            click.echo("✅ Database tables created.")

    @app.cli.command("seed")
    def seed():
        """Seed default admin + sample supervisor + sample students."""
        with app.app_context():
            # admin
            admin = User.query.filter_by(username="admin", role="admin").first()
            if not admin:
                admin = User(role="admin", username="admin", password_hash=generate_password_hash("admin123"), active=True)
                db.session.add(admin)

            # sample supervisor
            sup_u = User.query.filter_by(username="SUP1001", role="supervisor").first()
            if not sup_u:
                sup_u = User(role="supervisor", username="SUP1001", password_hash=generate_password_hash("sup123"), active=True)
                db.session.add(sup_u)
                db.session.flush()
                db.session.add(SupervisorProfile(user_id=sup_u.id, name="Default Supervisor", email="supervisor@example.com", phone="0610000000"))

            # sample students (official dataset)
            samples = [
                ("CS001", "Student One"),
                ("CS002", "Student Two"),
                ("CS003", "Student Three"),
            ]
            for sid, name in samples:
                sm = StudentMaster.query.get(sid)
                if not sm:
                    db.session.add(StudentMaster(
                        student_id=sid,
                        name=name,
                        gender="M",
                        phone="0610000000",
                        faculty="SIMAD",
                        program="CS",
                        batch="2025",
                        imported_at=datetime.utcnow(),
                    ))
            db.session.commit()
            click.echo("✅ Seed completed: admin/admin123, supervisor SUP1001/sup123, students CS001-CS003")
