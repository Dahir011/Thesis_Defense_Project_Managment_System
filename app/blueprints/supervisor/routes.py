from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import or_

from ...decorators import role_required
from ...extensions import db
from ...models import SupervisorAssignment, GroupMember, StudentMaster, Activity, ActivityTarget, Submission, TitleProposal, Group

bp = Blueprint("supervisor", __name__)

@bp.get("/dashboard")
@login_required
@role_required("supervisor")
def dashboard():
    assignments = SupervisorAssignment.query.filter_by(supervisor_user_id=current_user.id).all()
    group_codes = [a.group_code for a in assignments]
    groups_count = len(group_codes)
    subs_pending = Submission.query.join(Activity, Submission.activity_id==Activity.id)        .filter(Activity.created_by_role=="supervisor", Activity.created_by_user_id==current_user.id)        .filter(Submission.status=="Pending").count()
    return render_template("supervisor/dashboard.html", groups_count=groups_count, subs_pending=subs_pending)

@bp.get("/groups")
@login_required
@role_required("supervisor")
def groups():
    assignments = SupervisorAssignment.query.filter_by(
        supervisor_user_id=current_user.id
    ).all()

    group_rows = []

    for a in assignments:
        members = (
            db.session.query(StudentMaster)
            .join(GroupMember, GroupMember.student_id == StudentMaster.student_id)
            .filter(GroupMember.group_code == a.group_code)
            .all()
        )

        title = (
            TitleProposal.query
            .filter_by(
                group_code=a.group_code,
                status_admin="Approved",
                status_supervisor="Approved"
            )
            .order_by(TitleProposal.id.desc())
            .first()
        )

        group_rows.append({
            "assignment": a,
            "members": members,
            "title": title
        })

    return render_template(
        "supervisor/groups.html",
        group_rows=group_rows
    )

@bp.route("/activities", methods=["GET","POST"])
@login_required
@role_required("supervisor")
def activity_create():
    assignments = SupervisorAssignment.query.filter_by(supervisor_user_id=current_user.id).all()
    group_codes = [a.group_code for a in assignments]

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        desc = (request.form.get("description") or "").strip()
        start_at = request.form.get("start_at") or ""
        deadline_at = request.form.get("deadline_at") or ""
        require_pdf = True if request.form.get("require_pdf") == "on" else False
        scope_all = True if request.form.get("scope_all") == "on" else False
        targets = request.form.getlist("targets")

        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for("supervisor.activity_create"))

        def parse_dt(s):
            return datetime.fromisoformat(s) if s else None

        act = Activity(
            created_by_role="supervisor",
            created_by_user_id=current_user.id,
            title=title,
            description=desc,
            start_at=parse_dt(start_at),
            deadline_at=parse_dt(deadline_at),
            require_pdf=require_pdf,
            scope_all_groups=scope_all,
        )
        db.session.add(act)
        db.session.flush()

        if not scope_all:
            for g in targets:
                if g in group_codes:
                    db.session.add(ActivityTarget(activity_id=act.id, group_code=g))

        db.session.commit()
        flash("Activity published successfully.", "success")
        return redirect(url_for("supervisor.activity_create"))

    my_acts = Activity.query.filter_by(created_by_role="supervisor", created_by_user_id=current_user.id).order_by(Activity.id.desc()).all()
    return render_template("supervisor/activity_create.html", group_codes=group_codes, my_acts=my_acts)

@bp.get("/activity/<int:activity_id>/edit")
@login_required
@role_required("supervisor")
def edit_activity(activity_id):
    # Fetch the activity to be edited by the supervisor
    activity = Activity.query.get_or_404(activity_id)

    # Ensure the activity is created by the current supervisor
    if activity.created_by_role != "supervisor" or activity.created_by_user_id != current_user.id:
        flash("You don't have permission to edit this activity.", "danger")
        return redirect(url_for('supervisor.activity_create'))

    # Fetch all groups for the select field
    groups = Group.query.order_by(Group.group_code).all()

    # Get the selected groups for this activity
    selected_groups = [t.group_code for t in activity.targets]

    # Pre-fill the form with existing activity data
    start_at_formatted = activity.start_at.strftime('%Y-%m-%dT%H:%M') if activity.start_at else ""
    deadline_at_formatted = activity.deadline_at.strftime('%Y-%m-%dT%H:%M') if activity.deadline_at else ""

    return render_template(
        "supervisor/edit_activity.html",
        activity=activity,
        groups=groups,
        selected_groups=selected_groups,
        start_at=start_at_formatted,
        deadline_at=deadline_at_formatted
    )


@bp.post("/activity/<int:activity_id>/update")
@login_required
@role_required("supervisor")
def update_activity(activity_id):
    # Fetch the activity to be updated by the supervisor
    activity = Activity.query.get_or_404(activity_id)

    # Ensure the activity is created by the current supervisor
    if activity.created_by_role != "supervisor" or activity.created_by_user_id != current_user.id:
        flash("You don't have permission to update this activity.", "danger")
        return redirect(url_for('supervisor.activity_create'))

    # Get data from the form
    activity.title = request.form.get("title")
    activity.description = request.form.get("description")
    activity.require_pdf = True if request.form.get("require_pdf") == "on" else False
    activity.scope_all_groups = True if request.form.get("scope_all") == "on" else False

    # Parse the dates
    def parse_dt(v):
        return datetime.fromisoformat(v) if v else None

    activity.start_at = parse_dt(request.form.get("start_at"))
    activity.deadline_at = parse_dt(request.form.get("deadline_at"))

    # Reset the targets (groups)
    ActivityTarget.query.filter_by(activity_id=activity.id).delete()

    # Add new targets if the scope is not for all groups
    if not activity.scope_all_groups:
        targets = request.form.getlist("targets")
        for g in targets:
            db.session.add(ActivityTarget(activity_id=activity.id, group_code=g))

    # Commit changes to the database
    db.session.commit()
    flash("Activity updated successfully.", "success")
    return redirect(url_for("supervisor.activity_create"))
 

@bp.post("/activity/<int:activity_id>/delete")
@login_required
@role_required("supervisor")
def delete_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)

    # Ensuring the activity is created by the supervisor
    if activity.created_by_role != "supervisor" or activity.created_by_user_id != current_user.id:
        flash("You don't have permission to delete this activity.", "danger")
        return redirect(url_for('supervisor.activity_create'))

    # Deleting the activity and associated targets
    ActivityTarget.query.filter_by(activity_id=activity.id).delete()
    db.session.delete(activity)
    db.session.commit()

    flash("Activity deleted successfully.", "warning")
    return redirect(url_for("supervisor.activity_create"))



@bp.get("/reports")
@login_required
@role_required("supervisor")
def reports():
    # submissions to my activities
    my_act_ids = [a.id for a in Activity.query.filter_by(created_by_role="supervisor", created_by_user_id=current_user.id).all()]
    subs = Submission.query.filter(Submission.activity_id.in_(my_act_ids)).order_by(Submission.submitted_at.desc()).limit(500).all()
    return render_template("supervisor/reports.html", subs=subs)

@bp.post("/reports/<int:sub_id>/mark")
@login_required
@role_required("supervisor")
def mark_submission(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    act = Activity.query.get(sub.activity_id)
    if not act or act.created_by_role != "supervisor" or act.created_by_user_id != current_user.id:
        flash("Not allowed.", "danger")
        return redirect(url_for("supervisor.reports"))
    sub.status="Marked"
    sub.marked_by_user_id=current_user.id
    sub.marked_at=datetime.utcnow()
    db.session.commit()
    flash("Marked successfully.", "success")
    return redirect(url_for("supervisor.reports"))

@bp.post("/reports/<int:sub_id>/reject")
@login_required
@role_required("supervisor")
def reject_submission(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    act = Activity.query.get(sub.activity_id)
    if not act or act.created_by_role != "supervisor" or act.created_by_user_id != current_user.id:
        flash("Not allowed.", "danger")
        return redirect(url_for("supervisor.reports"))
    sub.status="Rejected"
    sub.marked_by_user_id=current_user.id
    sub.marked_at=datetime.utcnow()
    db.session.commit()
    flash("Rejected. Students may resubmit if deadline allows.", "warning")
    return redirect(url_for("supervisor.reports"))

@bp.get("/title-approvals")
@login_required
@role_required("supervisor")
def title_approvals():
    assignments = SupervisorAssignment.query.filter_by(supervisor_user_id=current_user.id).all()
    group_codes = [a.group_code for a in assignments]
    props = TitleProposal.query.filter(TitleProposal.group_code.in_(group_codes)).filter(TitleProposal.status_admin=="Approved").order_by(TitleProposal.id.desc()).all()
    return render_template("supervisor/title_approvals.html", props=props)

@bp.post("/title-approvals/<int:tp_id>/approve")
@login_required
@role_required("supervisor")
def approve_title(tp_id):
    tp = TitleProposal.query.get_or_404(tp_id)
    a = SupervisorAssignment.query.filter_by(group_code=tp.group_code, supervisor_user_id=current_user.id).first()
    if not a:
        flash("Not allowed.", "danger")
        return redirect(url_for("supervisor.title_approvals"))
    tp.status_supervisor="Approved"
    tp.last_action_at=datetime.utcnow()
    db.session.commit()
    flash("Title approved.", "success")
    return redirect(url_for("supervisor.title_approvals"))

@bp.post("/title-approvals/<int:tp_id>/reject")
@login_required
@role_required("supervisor")
def reject_title(tp_id):
    tp = TitleProposal.query.get_or_404(tp_id)
    a = SupervisorAssignment.query.filter_by(group_code=tp.group_code, supervisor_user_id=current_user.id).first()
    if not a:
        flash("Not allowed.", "danger")
        return redirect(url_for("supervisor.title_approvals"))
    tp.status_supervisor="Rejected"
    tp.last_action_at=datetime.utcnow()
    db.session.commit()
    flash("Title rejected. Group can submit a new title.", "warning")
    return redirect(url_for("supervisor.title_approvals"))
