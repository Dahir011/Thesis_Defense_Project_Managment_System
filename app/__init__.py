from flask import Flask
from flask_wtf.csrf import generate_csrf
from .config import Config
from .extensions import db, login_manager, csrf
from .models import User
from .commands import register_commands

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)
    
    # Ensure upload folders exist to avoid FileNotFoundError on first upload
    import os
    base_upload = app.config.get("UPLOAD_FOLDER")
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")

    os.makedirs(base_upload, exist_ok=True)
    os.makedirs(os.path.join(base_upload, "submissions"), exist_ok=True)
    os.makedirs(os.path.join(base_upload, "profiles"), exist_ok=True)

    # init extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.student_login"

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    # Make csrf_token available to all templates
    @app.context_processor
    def inject_csrf():
        return dict(csrf_token=generate_csrf)

    # Blueprints
    from .blueprints.main.routes import bp as main_bp
    from .blueprints.auth.routes import bp as auth_bp
    from .blueprints.student.routes import bp as student_bp
    from .blueprints.supervisor.routes import bp as supervisor_bp
    from .blueprints.admin.routes import bp as admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(supervisor_bp, url_prefix="/supervisor")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    register_commands(app)
    return app
