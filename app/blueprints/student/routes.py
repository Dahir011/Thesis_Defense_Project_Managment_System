from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from datetime import datetime
import os
from sqlalchemy import or_

from ...decorators import role_required
from ...extensions import db
from ...models import (
    StudentAccount, StudentMaster, Group, GroupMember, SupervisorAssignment,
    Activity, ActivityTarget, Submission, TeamRequest, TitleProposal, TitleArchive, TitleSelectionWindow, SupervisorProfile, User
)
from ...utils import secure_save, allowed_file

bp = Blueprint("student", __name__)

def _student_account():
    return StudentAccount.query.filter_by(user_id=current_user.id).first()

def _group_code():
    acc = _student_account()
    return acc.group_code if acc else None

@bp.get("/dashboard")
@login_required
@role_required("student")
def dashboard():
    acc = _student_account()
    group_code = acc.group_code if acc else None

    group_members = []
    assignment = None
    supervisor_profile = None
    title = None

    if group_code:
        group_members = GroupMember.query.filter_by(group_code=group_code).all()

        assignment = SupervisorAssignment.query.filter_by(group_code=group_code).first()
        if assignment:
            supervisor_profile = SupervisorProfile.query.filter_by(
                user_id=assignment.supervisor_user_id
            ).first()

        title = TitleProposal.query.filter_by(
            group_code=group_code,
            status_admin="Approved",
            status_supervisor="Approved"
        ).order_by(TitleProposal.id.desc()).first()

    # activities
    activities = []
    submitted_ids = set()

    if group_code:
        subs = Submission.query.filter_by(group_code=group_code).all()
        submitted_ids = {s.activity_id for s in subs}

        target_ids = [
            t.activity_id for t in
            ActivityTarget.query.filter_by(group_code=group_code).all()
        ]

        activities = Activity.query.filter(
            or_(
                Activity.scope_all_groups == True,
                Activity.id.in_(target_ids)
            )
        ).order_by(Activity.deadline_at.asc()).all()

    # title window
    win = TitleSelectionWindow.query.order_by(
        TitleSelectionWindow.id.desc()
    ).first()
    title_open = bool(win and win.is_open)

    return render_template(
        "student/dashboard.html",
        acc=acc,
        group_code=group_code,
        group_members=group_members,
        assignment=assignment,
        supervisor=supervisor_profile,
        title=title,
        activities=activities,
        submitted_ids=submitted_ids,
        title_open=title_open,
    )

@bp.route("/teamup", methods=["GET","POST"])
@login_required
@role_required("student")
def teamup():
    acc = _student_account()
    if acc.group_code:
        flash("You are already in a group.", "info")
        return redirect(url_for("student.dashboard"))

    q = (request.args.get("q") or "").strip()
    # available students: in master, have account, but group_code is null and not current user
    candidates_q = db.session.query(StudentAccount, StudentMaster).join(StudentMaster, StudentAccount.student_id==StudentMaster.student_id)        .filter(StudentAccount.group_code.is_(None)).filter(StudentAccount.user_id != current_user.id)

    if q:
        candidates_q = candidates_q.filter(or_(StudentMaster.name.ilike(f"%{q}%"), StudentMaster.student_id.ilike(f"%{q}%")))
    candidates = candidates_q.limit(50).all()

    if request.method == "POST":
        receiver_id = request.form.get("receiver_student_id")
        if not receiver_id:
            return redirect(url_for("student.teamup"))
        # validate receiver available
        recv_acc = StudentAccount.query.filter_by(student_id=receiver_id).first()
        if not recv_acc or recv_acc.group_code:
            flash("Student not available for team up.", "danger")
            return redirect(url_for("student.teamup"))
        # prevent duplicate pending
        existing = TeamRequest.query.filter_by(requester_student_id=acc.student_id, receiver_student_id=receiver_id, status="Pending").first()
        if existing:
            flash("Request already sent.", "warning")
            return redirect(url_for("student.teamup"))
        tr = TeamRequest(requester_student_id=acc.student_id, receiver_student_id=receiver_id, status="Pending")
        db.session.add(tr)
        db.session.commit()
        flash("Team request sent.", "success")
        return redirect(url_for("student.teamup"))

    return render_template("student/teamup.html", acc=acc, candidates=candidates, q=q)

@bp.get("/requests")
@login_required
@role_required("student")
def requests_inbox():
    acc = _student_account()
    inbox = TeamRequest.query.filter_by(receiver_student_id=acc.student_id, status="Pending").order_by(TeamRequest.created_at.desc()).all()
    sent = TeamRequest.query.filter_by(requester_student_id=acc.student_id).order_by(TeamRequest.created_at.desc()).limit(50).all()
    return render_template("student/requests.html", acc=acc, inbox=inbox, sent=sent)

@bp.post("/requests/<int:req_id>/accept")
@login_required
@role_required("student")
def accept_request(req_id):
    acc = _student_account()
    if acc.group_code:
        flash("You are already in a group.", "danger")
        return redirect(url_for("student.requests_inbox"))

    tr = TeamRequest.query.get_or_404(req_id)
    if tr.receiver_student_id != acc.student_id or tr.status != "Pending":
        flash("Invalid request.", "danger")
        return redirect(url_for("student.requests_inbox"))

    # requester must still be ungrouped
    req_acc = StudentAccount.query.filter_by(student_id=tr.requester_student_id).first()
    if not req_acc or req_acc.group_code:
        tr.status="Declined"
        db.session.commit()
        flash("Requester is no longer available. Request declined.", "warning")
        return redirect(url_for("student.requests_inbox"))

    # create group
    group_code = f"G{datetime.utcnow().strftime('%y%m%d')}{req_id:04d}"
    grp = Group(group_code=group_code)
    db.session.add(grp)
    db.session.flush()

    for sid in [tr.requester_student_id, tr.receiver_student_id]:
        db.session.add(GroupMember(group_code=group_code, student_id=sid))
        # set group_code on accounts
        sacc = StudentAccount.query.filter_by(student_id=sid).first()
        if sacc:
            sacc.group_code = group_code

    tr.status="Accepted"
    db.session.commit()
    flash(f"Team created successfully. Group code: {group_code}", "success")
    return redirect(url_for("student.dashboard"))

@bp.post("/requests/<int:req_id>/decline")
@login_required
@role_required("student")
def decline_request(req_id):
    acc = _student_account()
    tr = TeamRequest.query.get_or_404(req_id)
    if tr.receiver_student_id != acc.student_id or tr.status != "Pending":
        flash("Invalid request.", "danger")
        return redirect(url_for("student.requests_inbox"))
    tr.status="Declined"
    db.session.commit()
    flash("Request declined.", "info")
    return redirect(url_for("student.requests_inbox"))

@bp.route("/titles", methods=["GET","POST"])
@login_required
@role_required("student")
def titles():
    acc = _student_account()
    group_code = acc.group_code
    if not group_code:
        flash("You must be in a group to access titles.", "warning")
        return redirect(url_for("student.dashboard"))

    # selection window
    win = TitleSelectionWindow.query.order_by(TitleSelectionWindow.id.desc()).first()
    title_open = bool(win and win.is_open)

    # current proposal
    current = TitleProposal.query.filter_by(group_code=group_code).order_by(TitleProposal.id.desc()).first()

    if request.method == "POST":
        if not title_open:
            flash("Title selection is currently closed.", "danger")
            return redirect(url_for("student.titles"))
        if current and current.status_admin == "Pending":
            flash("You already have a pending title request.", "warning")
            return redirect(url_for("student.titles"))
        if current and current.status_supervisor == "Approved":
            flash("Your title is already fully approved.", "info")
            return redirect(url_for("student.titles"))

        title = (request.form.get("title") or "").strip()
        project_type = (request.form.get("project_type") or "").strip()
        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for("student.titles"))
        tp = TitleProposal(group_code=group_code, title=title, project_type=project_type, status_admin="Pending", status_supervisor="Pending")
        db.session.add(tp)
        db.session.commit()
        flash("Title submitted for admin review.", "success")
        return redirect(url_for("student.titles"))

    # taken titles combined
    search = (request.args.get("q") or "").strip()
    archive_q = TitleArchive.query
    approved_q = TitleProposal.query.filter_by(status_admin="Approved", status_supervisor="Approved")
    if search:
        archive_q = archive_q.filter(TitleArchive.title.ilike(f"%{search}%"))
        approved_q = approved_q.filter(TitleProposal.title.ilike(f"%{search}%"))
    archive = archive_q.order_by(TitleArchive.id.desc()).limit(200).all()
    approved = approved_q.order_by(TitleProposal.id.desc()).limit(200).all()

    return render_template("student/titles.html", acc=acc, group_code=group_code, title_open=title_open, current=current, archive=archive, approved=approved, search=search)

@bp.get("/activities")
@login_required
@role_required("student")
def activities():
    acc = _student_account()
    group_code = acc.group_code
    if not group_code:
        flash("You must be in a group.", "warning")
        return redirect(url_for("student.dashboard"))

    # activities target group or all
    targets = ActivityTarget.query.filter_by(group_code=group_code).all()
    target_ids = [t.activity_id for t in targets]
    acts = Activity.query.filter(
        or_(Activity.scope_all_groups==True, Activity.id.in_(target_ids))
    ).order_by(Activity.deadline_at.asc()).all()
    subs = Submission.query.filter_by(group_code=group_code).order_by(Submission.submitted_at.desc()).all()
    subs_by_act = {s.activity_id: s for s in subs}

    return render_template("student/activities.html", acc=acc, group_code=group_code, acts=acts, subs_by_act=subs_by_act)

@bp.route("/activities/<int:activity_id>/submit", methods=["GET","POST"])
@login_required
@role_required("student")
def submit_activity(activity_id):
    acc = _student_account()
    group_code = acc.group_code
    if not group_code:
        flash("You must be in a group.", "warning")
        return redirect(url_for("student.dashboard"))

    act = Activity.query.get_or_404(activity_id)

    # eligibility: target or all
    allowed = act.scope_all_groups
    if not allowed:
        allowed = ActivityTarget.query.filter_by(activity_id=activity_id, group_code=group_code).first() is not None
    if not allowed:
        flash("This activity is not assigned to your group.", "danger")
        return redirect(url_for("student.activities"))

    # check existing submission
    sub = Submission.query.filter_by(activity_id=activity_id, group_code=group_code).order_by(Submission.id.desc()).first()

    now = datetime.utcnow()
    if act.deadline_at and now > act.deadline_at and (not sub or sub.status != "Marked"):
        flash("Deadline has passed. Submission is locked.", "danger")
        return redirect(url_for("student.activities"))

    if request.method == "POST":
        # allow resubmit only if not marked and deadline not passed
        if sub and sub.status == "Marked":
            flash("This activity is already marked. You cannot resubmit.", "danger")
            return redirect(url_for("student.activities"))

        file = request.files.get("file")
        if act.require_pdf:
            if not file or not file.filename:
                flash("PDF file is required for this activity.", "danger")
                return redirect(url_for("student.submit_activity", activity_id=activity_id))
            if not allowed_file(file.filename, set(["pdf"])):
                flash("Only PDF files are allowed.", "danger")
                return redirect(url_for("student.submit_activity", activity_id=activity_id))

        file_path=None
        if file and file.filename:
            upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "submissions", group_code)
            file_path = secure_save(file, upload_dir, f"activity_{activity_id}_{acc.student_id}_{file.filename}")

        if not sub:
            sub = Submission(activity_id=activity_id, group_code=group_code, submitted_by_student_id=acc.student_id, file_path=file_path, status="Pending")
            db.session.add(sub)
        else:
            sub.file_path = file_path or sub.file_path
            sub.submitted_at = datetime.utcnow()
            sub.status = "Pending"
            sub.resubmission_count = (sub.resubmission_count or 0) + 1

        db.session.commit()
        flash("Submission saved successfully.", "success")
        return redirect(url_for("student.activities"))

    return render_template("student/activity_submit.html", acc=acc, group_code=group_code, act=act, sub=sub)

@bp.get("/uploads/<path:filepath>")
@login_required
@role_required("student","admin","supervisor")
def download_upload(filepath):
    # simple safe serve from UPLOAD_FOLDER
    base = current_app.config["UPLOAD_FOLDER"]
    directory = os.path.dirname(os.path.join(base, filepath))
    filename = os.path.basename(filepath)
    return send_from_directory(directory, filename, as_attachment=True)
