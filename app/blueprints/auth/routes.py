from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash

from ...extensions import db
from ...models import User, StudentMaster, StudentAccount
from ...utils import initials_from_name, avatar_color, allowed_file, secure_save
import os

import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta

def send_verification_email(to_email: str, code: str):
    """
    Uses SMTP config from app.config:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_USE_TLS, SMTP_FROM
    """
    host = current_app.config.get("SMTP_HOST")
    port = int(current_app.config.get("SMTP_PORT", 587))
    user = current_app.config.get("SMTP_USER")
    password = current_app.config.get("SMTP_PASSWORD")
    use_tls = bool(current_app.config.get("SMTP_USE_TLS", True))
    from_email = current_app.config.get("SMTP_FROM") or user

    if not host or not user or not password or not from_email:
        raise RuntimeError("SMTP is not configured (SMTP_HOST/SMTP_USER/SMTP_PASSWORD/SMTP_FROM).")

    msg = EmailMessage()
    msg["Subject"] = "UPMS+ Email Verification Code"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(
        f"Your UPMS+ verification code is: {code}\n\n"
        f"This code expires in 10 minutes.\n"
        f"If you did not request this, ignore this email."
    )

    if use_tls:
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP_SSL(host, port) as s:
            s.login(user, password)
            s.send_message(msg)





bp = Blueprint("auth", __name__)

def _redirect_by_role(user: User):
    if user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    if user.role == "supervisor":
        return redirect(url_for("supervisor.dashboard"))
    return redirect(url_for("student.dashboard"))

@bp.route("/student/login", methods=["GET","POST"])
def student_login():
    if current_user.is_authenticated and current_user.role == "student":
        return redirect(url_for("student.dashboard"))
    if request.method == "POST":
        sid = (request.form.get("student_id") or "").strip()
        pwd = request.form.get("password") or ""
        user = User.query.filter_by(role="student", username=sid).first()
        if not user or not user.check_password(pwd):
            flash("Invalid Student ID or password.", "danger")
            return redirect(url_for("auth.student_login"))
        if not user.active:
            flash("Account is disabled.", "danger")
            return redirect(url_for("auth.student_login"))
        login_user(user)
        return _redirect_by_role(user)
    return render_template("auth/student_login.html")

@bp.route("/supervisor/login", methods=["GET","POST"])
def supervisor_login():
    if current_user.is_authenticated and current_user.role == "supervisor":
        return redirect(url_for("supervisor.dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        pwd = request.form.get("password") or ""
        user = User.query.filter_by(role="supervisor", username=username).first()
        if not user or not user.check_password(pwd):
            flash("Invalid username or password.", "danger")
            return redirect(url_for("auth.supervisor_login"))
        if not user.active:
            flash("Account is disabled.", "danger")
            return redirect(url_for("auth.supervisor_login"))
        login_user(user)
        return _redirect_by_role(user)
    return render_template("auth/supervisor_login.html")

@bp.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if current_user.is_authenticated and current_user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        pwd = request.form.get("password") or ""
        user = User.query.filter_by(role="admin", username=username).first()
        if not user or not user.check_password(pwd):
            flash("Invalid username or password.", "danger")
            return redirect(url_for("auth.admin_login"))
        if not user.active:
            flash("Account is disabled.", "danger")
            return redirect(url_for("auth.admin_login"))
        login_user(user)
        return _redirect_by_role(user)
    return render_template("auth/admin_login.html")

@bp.get("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.index"))

# --- Student 2-step account creation ---
@bp.route("/student/register", methods=["GET","POST"])
def student_register_step1():
    if request.method == "POST":
        sid = (request.form.get("student_id") or "").strip()
        master = StudentMaster.query.get(sid)
        if not master:
            flash("Student ID not found in official dataset. Contact admin.", "danger")
            return redirect(url_for("auth.student_register_step1"))

        existing = User.query.filter_by(role="student", username=sid).first()
        if existing:
            flash("Account already exists for this Student ID. Please login.", "warning")
            return redirect(url_for("auth.student_login"))

        session["register_sid"] = sid
        return redirect(url_for("auth.student_register_step2"))

    return render_template("auth/student_register_step1.html")

@bp.route("/student/register/confirm", methods=["GET","POST"])
def student_register_step2():
    sid = session.get("register_sid")
    if not sid:
        return redirect(url_for("auth.student_register_step1"))

    master = StudentMaster.query.get(sid)
    if not master:
        flash("Student record not found.", "danger")
        return redirect(url_for("auth.student_register_step1"))

    # If student has no email, cannot verify
    if not master.email:
        flash("This student record has no email. Contact admin to add email.", "danger")
        return redirect(url_for("auth.student_register_step1"))

    verified = bool(session.get("register_verified"))

    # Send code on first visit (or if expired/missing)
    def ensure_code_sent():
        now = datetime.utcnow()
        exp = session.get("register_code_exp")  # iso str
        has_code = session.get("register_code") is not None

        # already verified -> no need
        if session.get("register_verified"):
            return

        # if code exists and still valid -> do nothing
        if has_code and exp:
            try:
                exp_dt = datetime.fromisoformat(exp)
                if exp_dt > now:
                    return
            except Exception:
                pass

        # generate new code
        code = f"{random.randint(100000, 999999)}"
        session["register_code"] = code
        session["register_code_exp"] = (now + timedelta(minutes=10)).isoformat()
        session["register_code_attempts"] = 0

        send_verification_email(master.email, code)

    if request.method == "GET":
        try:
            ensure_code_sent()
        except Exception as e:
            flash(f"Email verification is not available: {e}", "danger")
        return render_template("auth/student_register_step2.html", master=master, verified=verified)

    # POST
    action = request.form.get("action") or ""

    # 1) Verify code
    if action == "verify_code":
        code_input = (request.form.get("verification_code") or "").strip()
        real_code = session.get("register_code")
        exp = session.get("register_code_exp")

        # basic checks
        if not real_code or not exp:
            flash("Verification code not found. Please resend code.", "danger")
            return redirect(url_for("auth.student_register_step2"))

        try:
            exp_dt = datetime.fromisoformat(exp)
        except Exception:
            flash("Verification code invalid. Please resend code.", "danger")
            return redirect(url_for("auth.student_register_step2"))

        if datetime.utcnow() > exp_dt:
            flash("Verification code expired. Please resend code.", "warning")
            return redirect(url_for("auth.student_register_step2"))

        attempts = int(session.get("register_code_attempts", 0))
        if attempts >= 5:
            flash("Too many wrong attempts. Please resend code.", "danger")
            return redirect(url_for("auth.student_register_step2"))

        if code_input != str(real_code):
            session["register_code_attempts"] = attempts + 1
            flash("Incorrect verification code.", "danger")
            return redirect(url_for("auth.student_register_step2"))

        # success
        session["register_verified"] = True
        flash("Email verified successfully. Now create your password.", "success")
        return redirect(url_for("auth.student_register_step2"))

    # 2) Resend code
    if action == "resend_code":
        try:
            # force new code
            session.pop("register_code", None)
            session.pop("register_code_exp", None)
            session.pop("register_code_attempts", None)
            ensure_code_sent()
            flash("New verification code sent to your student email.", "success")
        except Exception as e:
            flash(f"Failed to send email: {e}", "danger")
        return redirect(url_for("auth.student_register_step2"))

    # 3) Create account (only if verified)
    if not session.get("register_verified"):
        flash("Please verify your email first.", "danger")
        return redirect(url_for("auth.student_register_step2"))

    # ---- your existing create account logic ----
    pwd = request.form.get("password") or ""
    pwd2 = request.form.get("confirm_password") or ""
    if not pwd or len(pwd) < 6:
        flash("Password must be at least 6 characters.", "danger")
        return redirect(url_for("auth.student_register_step2"))
    if pwd != pwd2:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("auth.student_register_step2"))

    existing = User.query.filter_by(role="student", username=sid).first()
    if existing:
        flash("Account already exists for this Student ID. Please login.", "warning")
        return redirect(url_for("auth.student_login"))

    user = User(role="student", username=sid, password_hash=generate_password_hash(pwd))
    db.session.add(user)
    db.session.flush()

    photo = request.files.get("photo")
    photo_path = None
    initials = initials_from_name(master.name)
    color = avatar_color(sid)

    if photo and photo.filename:
        if not allowed_file(photo.filename, set(current_app.config["ALLOWED_IMAGE_EXTENSIONS"])):
            flash("Profile photo must be an image (png/jpg/jpeg/webp).", "danger")
            db.session.rollback()
            return redirect(url_for("auth.student_register_step2"))
        upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "profiles")
        photo_path = secure_save(photo, upload_dir, f"{sid}_{photo.filename}")

    acc = StudentAccount(
        user_id=user.id,
        student_id=sid,
        photo_path=photo_path,
        avatar_initials=initials,
        avatar_color=color,
    )
    db.session.add(acc)
    db.session.commit()

    # clear session
    session.pop("register_sid", None)
    session.pop("register_code", None)
    session.pop("register_code_exp", None)
    session.pop("register_code_attempts", None)
    session.pop("register_verified", None)

    flash("Account created successfully. Please login.", "success")
    return redirect(url_for("auth.student_login"))
