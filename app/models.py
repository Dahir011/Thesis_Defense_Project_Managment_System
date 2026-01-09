from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.Enum("admin","supervisor","student", name="role_enum"), nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)  # admin/supervisor username OR student_id
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student_account = db.relationship("StudentAccount", back_populates="user", uselist=False)
    supervisor_profile = db.relationship("SupervisorProfile", back_populates="user", uselist=False)

    def set_password(self, pwd: str):
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd: str) -> bool:
        return check_password_hash(self.password_hash, pwd)

class StudentMaster(db.Model):
    __tablename__ = "students_master"
    student_id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    gender = db.Column(db.String(20))
    phone = db.Column(db.String(40))
    email = db.Column(db.String(120))   # ✅ NEW
    faculty = db.Column(db.String(120))
    program = db.Column(db.String(120))
    batch = db.Column(db.String(40))
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship("StudentAccount", back_populates="master", uselist=False)

class StudentAccount(db.Model):
    __tablename__ = "student_accounts"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    student_id = db.Column(db.String(32), db.ForeignKey("students_master.student_id"), unique=True, nullable=False)
    photo_path = db.Column(db.String(255))
    avatar_initials = db.Column(db.String(8))
    avatar_color = db.Column(db.String(20))
    group_code = db.Column(db.String(20), db.ForeignKey("groups.group_code"))

    user = db.relationship("User", back_populates="student_account")
    master = db.relationship("StudentMaster", back_populates="account")
    group = db.relationship("Group", back_populates="members_accounts")

class SupervisorProfile(db.Model):
    __tablename__ = "supervisor_profiles"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(40))

    user = db.relationship("User", back_populates="supervisor_profile")

class Group(db.Model):
    __tablename__ = "groups"
    group_code = db.Column(db.String(20), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    members_accounts = db.relationship("StudentAccount", back_populates="group")
    assignments = db.relationship("SupervisorAssignment", back_populates="group", cascade="all, delete-orphan")

class GroupMember(db.Model):
    __tablename__ = "group_members"
    id = db.Column(db.Integer, primary_key=True)
    group_code = db.Column(db.String(20), db.ForeignKey("groups.group_code"), nullable=False)
    student_id = db.Column(db.String(32), db.ForeignKey("students_master.student_id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("Group", back_populates="members")
    student = db.relationship("StudentMaster")

class SupervisorAssignment(db.Model):
    __tablename__ = "supervisor_assignments"
    id = db.Column(db.Integer, primary_key=True)
    group_code = db.Column(db.String(20), db.ForeignKey("groups.group_code"), nullable=False, unique=True)
    supervisor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("Group", back_populates="assignments")
    supervisor = db.relationship("User")

class Activity(db.Model):
    __tablename__ = "activities"
    id = db.Column(db.Integer, primary_key=True)
    created_by_role = db.Column(db.Enum("admin","supervisor", name="activity_creator_enum"), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_at = db.Column(db.DateTime)
    deadline_at = db.Column(db.DateTime)
    require_pdf = db.Column(db.Boolean, default=False)
    scope_all_groups = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    targets = db.relationship("ActivityTarget", back_populates="activity", cascade="all, delete-orphan")
    submissions = db.relationship("Submission", back_populates="activity", cascade="all, delete-orphan")

class ActivityTarget(db.Model):
    __tablename__ = "activity_targets"
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=False)
    group_code = db.Column(db.String(20), db.ForeignKey("groups.group_code"), nullable=False)

    activity = db.relationship("Activity", back_populates="targets")
    group = db.relationship("Group")

class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=False)
    group_code = db.Column(db.String(20), db.ForeignKey("groups.group_code"), nullable=False)
    submitted_by_student_id = db.Column(db.String(32), db.ForeignKey("students_master.student_id"), nullable=False)
    file_path = db.Column(db.String(255))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.Enum("Pending","Marked","Rejected", name="submission_status_enum"), default="Pending")
    marked_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    marked_at = db.Column(db.DateTime)
    feedback = db.Column(db.Text)
    resubmission_count = db.Column(db.Integer, default=0)

    activity = db.relationship("Activity", back_populates="submissions")
    group = db.relationship("Group")
    marker = db.relationship("User", foreign_keys=[marked_by_user_id])

class TitleSelectionWindow(db.Model):
    __tablename__ = "title_selection_windows"
    id = db.Column(db.Integer, primary_key=True)
    is_open = db.Column(db.Boolean, default=False)
    scope_all_groups = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))

class TitleProposal(db.Model):
    __tablename__ = "title_proposals"
    id = db.Column(db.Integer, primary_key=True)
    group_code = db.Column(db.String(20), db.ForeignKey("groups.group_code"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    project_type = db.Column(db.String(80))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    status_admin = db.Column(db.Enum("Pending","Approved","Rejected", name="title_admin_enum"), default="Pending")
    status_supervisor = db.Column(db.Enum("Pending","Approved","Rejected", name="title_super_enum"), default="Pending")
    last_action_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("Group")

class TitleArchive(db.Model):
    __tablename__ = "titles_archive"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    project_type = db.Column(db.String(80))
    year = db.Column(db.String(10))
    department = db.Column(db.String(120))
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)

class TeamRequest(db.Model):
    __tablename__ = "team_requests"
    id = db.Column(db.Integer, primary_key=True)
    requester_student_id = db.Column(db.String(32), db.ForeignKey("students_master.student_id"), nullable=False)
    receiver_student_id = db.Column(db.String(32), db.ForeignKey("students_master.student_id"), nullable=False)
    status = db.Column(db.Enum("Pending","Accepted","Declined", name="team_request_enum"), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    requester = db.relationship("StudentMaster", foreign_keys=[requester_student_id])
    receiver = db.relationship("StudentMaster", foreign_keys=[receiver_student_id])


