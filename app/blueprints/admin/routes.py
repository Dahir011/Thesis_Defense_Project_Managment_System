from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime
import io
import pandas as pd
from sqlalchemy import or_

from ...decorators import role_required
from ...extensions import db
from ...models import (
    User, SupervisorProfile, StudentMaster, StudentAccount, Group, GroupMember,
    SupervisorAssignment, Activity, ActivityTarget, Submission,
    TitleSelectionWindow, TitleProposal, TitleArchive
)

bp = Blueprint("admin", __name__)

@bp.get("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    stats = {
        "students_master": StudentMaster.query.count(),
        "student_accounts": User.query.filter_by(role="student").count(),
        "supervisors": User.query.filter_by(role="supervisor").count(),
        "groups": Group.query.count(),
        "activities": Activity.query.count(),
        "submissions_pending": Submission.query.filter_by(status="Pending").count()
    }
    return render_template("admin/dashboard.html", stats=stats)

@bp.route("/registration", methods=["GET","POST"])
@login_required
@role_required("admin")
def registration():
    tab = request.args.get("tab","supervisor")

    if request.method == "POST" and tab == "supervisor":
        name = (request.form.get("name") or "").strip()
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        if not (name and username and password):
            flash("Name, username, and password are required.", "danger")
            return redirect(url_for("admin.registration", tab="supervisor"))
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("admin.registration", tab="supervisor"))
        user = User(role="supervisor", username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.flush()
        db.session.add(SupervisorProfile(user_id=user.id, name=name, email=email, phone=phone))
        db.session.commit()
        flash("Supervisor created.", "success")
        return redirect(url_for("admin.supervisors"))

    if request.method == "POST" and tab == "third_student":
        group_code = request.form.get("group_code")
        student_id = (request.form.get("student_id") or "").strip()
        if not group_code or not student_id:
            flash("Group code and Student ID are required.", "danger")
            return redirect(url_for("admin.registration", tab="third_student"))
        grp = Group.query.get(group_code)
        if not grp:
            flash("Group not found.", "danger")
            return redirect(url_for("admin.registration", tab="third_student"))
        master = StudentMaster.query.get(student_id)
        if not master:
            flash("Student not in official dataset.", "danger")
            return redirect(url_for("admin.registration", tab="third_student"))
        acc = StudentAccount.query.filter_by(student_id=student_id).first()
        if acc and acc.group_code:
            flash("Student already in a group.", "danger")
            return redirect(url_for("admin.registration", tab="third_student"))
        # member limit
        current_members = GroupMember.query.filter_by(group_code=group_code).count()
        max_members = int(request.form.get("max_members") or 3)
        if current_members >= max_members:
            flash("Group member limit reached.", "danger")
            return redirect(url_for("admin.registration", tab="third_student"))

        if not GroupMember.query.filter_by(group_code=group_code, student_id=student_id).first():
            db.session.add(GroupMember(group_code=group_code, student_id=student_id))
        if acc:
            acc.group_code = group_code
        db.session.commit()
        flash("Student added to group.", "success")
        return redirect(url_for("admin.students"))

    groups = Group.query.order_by(Group.created_at.desc()).all()
    return render_template("admin/registration.html", tab=tab, groups=groups)

@bp.get("/supervisors")
@login_required
@role_required("admin")
def supervisors():
    supervisors = db.session.query(User, SupervisorProfile).join(SupervisorProfile, SupervisorProfile.user_id==User.id)        .filter(User.role=="supervisor").order_by(User.id.desc()).all()
    return render_template("admin/supervisors.html", supervisors=supervisors)

@bp.post("/supervisors/<int:user_id>/delete")
@login_required
@role_required("admin")
def delete_supervisor(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != "supervisor":
        flash("Invalid.", "danger")
        return redirect(url_for("admin.supervisors"))
    SupervisorProfile.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash("Supervisor deleted.", "success")
    return redirect(url_for("admin.supervisors"))

@bp.post("/supervisors/<int:user_id>/reset")
@login_required
@role_required("admin")
def reset_supervisor_password(user_id):
    new_pass = request.form.get("new_password") or "sup123"
    user = User.query.get_or_404(user_id)
    if user.role != "supervisor":
        flash("Invalid.", "danger")
        return redirect(url_for("admin.supervisors"))
    user.password_hash = generate_password_hash(new_pass)
    db.session.commit()
    flash("Password reset.", "success")
    return redirect(url_for("admin.supervisors"))

@bp.route("/students", methods=["GET"])
@login_required
@role_required("admin")
def students():
    flt = request.args.get("filter","all")
    q = (request.args.get("q") or "").strip()

    # base join
    join_q = db.session.query(StudentMaster, StudentAccount).outerjoin(StudentAccount, StudentAccount.student_id==StudentMaster.student_id)
    if q:
        join_q = join_q.filter(or_(StudentMaster.student_id.ilike(f"%{q}%"), StudentMaster.name.ilike(f"%{q}%")))

    if flt == "not_registered":
        join_q = join_q.filter(StudentAccount.user_id.is_(None))
    elif flt == "in_team":
        join_q = join_q.filter(StudentAccount.group_code.isnot(None))
    elif flt == "no_team":
        join_q = join_q.filter(StudentAccount.user_id.isnot(None)).filter(StudentAccount.group_code.is_(None))

    rows = join_q.order_by(StudentMaster.student_id.asc()).limit(1000).all()
    return render_template("admin/students.html", rows=rows, flt=flt, q=q)

@bp.get("/students/export")
@login_required
@role_required("admin")
def export_not_registered():
    join_q = db.session.query(StudentMaster).outerjoin(StudentAccount, StudentAccount.student_id==StudentMaster.student_id)        .filter(StudentAccount.user_id.is_(None)).all()
    data = [{"student_id": s.student_id, "name": s.name, "gender": s.gender, "phone": s.phone,"email": s.email, "faculty": s.faculty, "program": s.program, "batch": s.batch} for s in join_q]
    df = pd.DataFrame(data)
    out = io.BytesIO()
    df.to_csv(out, index=False)
    out.seek(0)
    return send_file(out, mimetype="text/csv", as_attachment=True, download_name="non_registered_students.csv")

@bp.route("/assigning", methods=["GET", "POST"])
@login_required
@role_required("admin")
def assigning():
    if request.method == "POST":
        action = request.form.get("action")
        
        # Handle supervisor assignment
        if action == "assign_supervisor":
            group_code = request.form.get("group_code")
            supervisor_id = int(request.form.get("supervisor_user_id"))
            if not group_code or not supervisor_id:
                flash("Group and supervisor required.", "danger")
                return redirect(url_for("admin.assigning"))
            # upsert assignment
            existing = SupervisorAssignment.query.filter_by(group_code=group_code).first()
            if existing:
                existing.supervisor_user_id = supervisor_id
                existing.assigned_at = datetime.utcnow()
            else:
                db.session.add(SupervisorAssignment(group_code=group_code, supervisor_user_id=supervisor_id))
            db.session.commit()
            flash("Supervisor assigned.", "success")
            return redirect(url_for("admin.assigning"))

        # Handle activity creation
        if action == "create_activity":
            title = request.form.get("title")
            description = request.form.get("description")
            start_at = request.form.get("start_at")
            deadline_at = request.form.get("deadline_at")
            require_pdf = "require_pdf" in request.form
            scope_all = "scope_all" in request.form
            targets = request.form.getlist("targets")

            if not title or not description:
                flash("Title and description are required.", "danger")
                return redirect(url_for("admin.assigning"))

            # Get the logged-in admin's user ID
            created_by_user_id = current_user.id

            # Create activity
            activity = Activity(
                title=title,
                description=description,
                start_at=start_at,
                deadline_at=deadline_at,
                require_pdf=require_pdf,
                scope_all_groups=scope_all,
                created_by_role="admin",
                created_by_user_id=created_by_user_id  # Set the logged-in admin's ID here
            )
            db.session.add(activity)
            db.session.commit()

            # If scope is not "all", assign to selected groups
            if not scope_all:
                for group_code in targets:
                    db.session.add(ActivityGroup(activity_id=activity.id, group_code=group_code))

            db.session.commit()
            flash("Activity created.", "success")
            return redirect(url_for("admin.assigning"))

    groups = Group.query.order_by(Group.created_at.desc()).all()
    # Fetching group members along with students
    for group in groups:
        group.members_details = [
            {"student_id": member.student_id, "name": member.student.name, "batch": member.student.batch}
            for member in group.members
        ]
    
    supervisors = User.query.filter_by(role="supervisor").order_by(User.id.desc()).all()
    activities = Activity.query.filter_by(created_by_role="admin").order_by(Activity.id.desc()).limit(50).all()
    return render_template("admin/assigning.html", groups=groups, supervisors=supervisors, activities=activities)

@bp.get("/activity")
@login_required
@role_required("admin")
def activity():
    subs = Submission.query.order_by(Submission.submitted_at.desc()).limit(500).all()
    return render_template("admin/activity.html", subs=subs)

@bp.post("/activity/<int:sub_id>/mark")
@login_required
@role_required("admin")
def mark_sub(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    sub.status="Marked"
    sub.marked_by_user_id=current_user.id
    sub.marked_at=datetime.utcnow()
    db.session.commit()
    flash("Marked.", "success")
    return redirect(url_for("admin.activity"))

@bp.post("/activity/<int:sub_id>/reject")
@login_required
@role_required("admin")
def reject_sub(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    sub.status="Rejected"
    sub.marked_by_user_id=current_user.id
    sub.marked_at=datetime.utcnow()
    db.session.commit()
    flash("Rejected.", "warning")
    return redirect(url_for("admin.activity"))

@bp.get("/activity/<int:activity_id>/edit")
@login_required
@role_required("admin")
def edit_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    groups = Group.query.order_by(Group.group_code).all()
    selected_groups = [t.group_code for t in activity.targets]

    return render_template(
        "admin/activity_edit.html",
        activity=activity,
        groups=groups,
        selected_groups=selected_groups
    )


@bp.post("/activity/<int:activity_id>/update")
@login_required
@role_required("admin")
def update_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)

    activity.title = request.form.get("title")
    activity.description = request.form.get("description")
    activity.require_pdf = True if request.form.get("require_pdf") == "on" else False
    activity.scope_all_groups = True if request.form.get("scope_all") == "on" else False

    def parse_dt(v):
        return datetime.fromisoformat(v) if v else None

    activity.start_at = parse_dt(request.form.get("start_at"))
    activity.deadline_at = parse_dt(request.form.get("deadline_at"))

    # reset targets
    ActivityTarget.query.filter_by(activity_id=activity.id).delete()

    if not activity.scope_all_groups:
        targets = request.form.getlist("targets")
        for g in targets:
            db.session.add(ActivityTarget(activity_id=activity.id, group_code=g))

    db.session.commit()
    flash("Activity updated successfully.", "success")
    return redirect(url_for("admin.assigning"))


@bp.post("/activity/<int:activity_id>/delete")
@login_required
@role_required("admin")
def delete_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)

    db.session.delete(activity)  # cascades to targets + submissions
    db.session.commit()

    flash("Activity deleted permanently.", "warning")
    return redirect(url_for("admin.assigning"))


@bp.route("/title-control", methods=["GET","POST"])
@login_required
@role_required("admin")
def title_control():
    if request.method == "POST":
        is_open = True if request.form.get("is_open") == "on" else False
        scope_all = True if request.form.get("scope_all") == "on" else False
        win = TitleSelectionWindow(is_open=is_open, scope_all_groups=scope_all, created_by=current_user.id)
        db.session.add(win)
        db.session.commit()
        flash("Title selection settings updated.", "success")
        return redirect(url_for("admin.title_control"))
    win = TitleSelectionWindow.query.order_by(TitleSelectionWindow.id.desc()).first()
    props = TitleProposal.query.order_by(TitleProposal.id.desc()).limit(200).all()
    return render_template("admin/title_control.html", win=win, props=props)

@bp.post("/title-control/<int:tp_id>/approve")
@login_required
@role_required("admin")
def approve_title(tp_id):
    tp = TitleProposal.query.get_or_404(tp_id)
    tp.status_admin="Approved"
    tp.last_action_at=datetime.utcnow()
    db.session.commit()
    flash("Approved and forwarded to supervisor.", "success")
    return redirect(url_for("admin.title_control"))

@bp.post("/title-control/<int:tp_id>/reject")
@login_required
@role_required("admin")
def reject_title(tp_id):
    tp = TitleProposal.query.get_or_404(tp_id)
    tp.status_admin="Rejected"
    tp.last_action_at=datetime.utcnow()
    db.session.commit()
    flash("Rejected. Group may resubmit.", "warning")
    return redirect(url_for("admin.title_control"))

@bp.get("/accounts")
@login_required
@role_required("admin")
def accounts():
    flt = request.args.get("role","all")
    q = (request.args.get("q") or "").strip()
    users_q = User.query
    if flt in ("admin","supervisor","student"):
        users_q = users_q.filter_by(role=flt)
    if q:
        users_q = users_q.filter(User.username.ilike(f"%{q}%"))
    users = users_q.order_by(User.id.desc()).limit(500).all()
    return render_template("admin/accounts.html", users=users, flt=flt, q=q)

@bp.post("/accounts/<int:user_id>/reset")
@login_required
@role_required("admin")
def reset_account(user_id):
    new_pass = request.form.get("new_password") or "newpass123"
    user = User.query.get_or_404(user_id)
    user.password_hash = generate_password_hash(new_pass)
    db.session.commit()
    flash("Password reset.", "success")
    return redirect(url_for("admin.accounts"))

@bp.post("/accounts/<int:user_id>/delete")
@login_required
@role_required("admin")
def delete_account(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin" and user.username == "admin":
        flash("Cannot delete default admin.", "danger")
        return redirect(url_for("admin.accounts"))
    db.session.delete(user)
    db.session.commit()
    flash("Account deleted.", "success")
    return redirect(url_for("admin.accounts"))

@bp.route("/import", methods=["GET","POST"])
@login_required
@role_required("admin")
def import_page():
    if request.method == "POST":
        kind = request.form.get("kind")
        f = request.files.get("file")
        if not f or not f.filename:
            flash("File required.", "danger")
            return redirect(url_for("admin.import_page"))
        try:
            if f.filename.lower().endswith(".csv"):
                df = pd.read_csv(f)
            else:
                df = pd.read_excel(f)
        except Exception as e:
            flash(f"Could not read file: {e}", "danger")
            return redirect(url_for("admin.import_page"))

        if kind == "students":
            required = ["student_id","name","gender","phone","email","faculty","program","batch"]
            missing = [c for c in required if c not in df.columns]
            if missing:
                flash(f"Missing columns: {missing}", "danger")
                return redirect(url_for("admin.import_page"))
            added=0
            for _, row in df.iterrows():
                sid=str(row["student_id"]).strip()
                if not sid:
                    continue
                sm = StudentMaster.query.get(sid)
                if not sm:
                    sm = StudentMaster(student_id=sid)
                    db.session.add(sm)
                    added += 1
                sm.name = str(row["name"]).strip()
                sm.gender = str(row.get("gender","")).strip()
                sm.phone = str(row.get("phone","")).strip()
                sm.email = str(row.get("email","")).strip()   # ✅ NEW
                sm.faculty = str(row.get("faculty","")).strip()
                sm.program = str(row.get("program","")).strip()
                sm.batch = str(row.get("batch","")).strip()
            db.session.commit()
            flash(f"Imported students. Added {added} new records.", "success")
            return redirect(url_for("admin.import_page"))

        if kind == "titles":
            required = ["title","project_type","year"]
            missing = [c for c in required if c not in df.columns]
            if missing:
                flash(f"Missing columns: {missing}", "danger")
                return redirect(url_for("admin.import_page"))
            added=0
            for _, row in df.iterrows():
                title=str(row["title"]).strip()
                if not title:
                    continue
                ta = TitleArchive(title=title, project_type=str(row.get("project_type","")).strip(), year=str(row.get("year","")).strip(), department=str(row.get("department","")).strip())
                db.session.add(ta)
                added += 1
            db.session.commit()
            flash(f"Imported titles archive: {added} rows.", "success")
            return redirect(url_for("admin.import_page"))

    return render_template("admin/import.html")
