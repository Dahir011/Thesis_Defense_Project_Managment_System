-- UPMS+ TeamUp Schema (MySQL / XAMPP)
-- This schema is aligned with the SQLAlchemy models in app/models.py

CREATE DATABASE IF NOT EXISTS upms_teamup
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE upms_teamup;

SET FOREIGN_KEY_CHECKS=0;

-- USERS
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  role ENUM('admin','supervisor','student') NOT NULL,
  username VARCHAR(64) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- OFFICIAL STUDENT DATASET
CREATE TABLE IF NOT EXISTS students_master (
  student_id VARCHAR(32) PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  gender VARCHAR(20) NULL,
  phone VARCHAR(40) NULL,
  faculty VARCHAR(120) NULL,
  program VARCHAR(120) NULL,
  batch VARCHAR(40) NULL,
  imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- STUDENT ACCOUNT PROFILE (1:1 with users, and 1:1 with students_master)
CREATE TABLE IF NOT EXISTS student_accounts (
  user_id INT PRIMARY KEY,
  student_id VARCHAR(32) NOT NULL UNIQUE,
  photo_path VARCHAR(255) NULL,
  avatar_initials VARCHAR(8) NULL,
  avatar_color VARCHAR(20) NULL,
  group_code VARCHAR(20) NULL,
  CONSTRAINT fk_sa_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_sa_master FOREIGN KEY (student_id) REFERENCES students_master(student_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- SUPERVISOR PROFILE (1:1 with users)
CREATE TABLE IF NOT EXISTS supervisor_profiles (
  user_id INT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(120) NULL,
  phone VARCHAR(40) NULL,
  CONSTRAINT fk_sp_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- GROUPS
CREATE TABLE IF NOT EXISTS groups (
  group_code VARCHAR(20) PRIMARY KEY,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS group_members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  group_code VARCHAR(20) NOT NULL,
  student_id VARCHAR(32) NOT NULL,
  joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_group_student (group_code, student_id),
  CONSTRAINT fk_gm_group FOREIGN KEY (group_code) REFERENCES groups(group_code) ON DELETE CASCADE,
  CONSTRAINT fk_gm_student FOREIGN KEY (student_id) REFERENCES students_master(student_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- TEAM UP REQUESTS
CREATE TABLE IF NOT EXISTS team_requests (
  id INT AUTO_INCREMENT PRIMARY KEY,
  requester_student_id VARCHAR(32) NOT NULL,
  receiver_student_id VARCHAR(32) NOT NULL,
  status ENUM('Pending','Accepted','Declined') NOT NULL DEFAULT 'Pending',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_tr_req FOREIGN KEY (requester_student_id) REFERENCES students_master(student_id) ON DELETE RESTRICT,
  CONSTRAINT fk_tr_rec FOREIGN KEY (receiver_student_id) REFERENCES students_master(student_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- SUPERVISOR ASSIGNMENTS (one supervisor per group)
CREATE TABLE IF NOT EXISTS supervisor_assignments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  group_code VARCHAR(20) NOT NULL UNIQUE,
  supervisor_user_id INT NOT NULL,
  assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_sa_group FOREIGN KEY (group_code) REFERENCES groups(group_code) ON DELETE CASCADE,
  CONSTRAINT fk_sa_supervisor FOREIGN KEY (supervisor_user_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ACTIVITIES
CREATE TABLE IF NOT EXISTS activities (
  id INT AUTO_INCREMENT PRIMARY KEY,
  created_by_role ENUM('admin','supervisor') NOT NULL,
  created_by_user_id INT NOT NULL,
  title VARCHAR(200) NOT NULL,
  description TEXT NULL,
  start_at DATETIME NULL,
  deadline_at DATETIME NULL,
  require_pdf TINYINT(1) NOT NULL DEFAULT 0,
  scope_all_groups TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_act_creator FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS activity_targets (
  id INT AUTO_INCREMENT PRIMARY KEY,
  activity_id INT NOT NULL,
  group_code VARCHAR(20) NOT NULL,
  CONSTRAINT fk_at_activity FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
  CONSTRAINT fk_at_group FOREIGN KEY (group_code) REFERENCES groups(group_code) ON DELETE CASCADE
) ENGINE=InnoDB;

-- SUBMISSIONS
CREATE TABLE IF NOT EXISTS submissions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  activity_id INT NOT NULL,
  group_code VARCHAR(20) NOT NULL,
  submitted_by_student_id VARCHAR(32) NOT NULL,
  file_path VARCHAR(255) NULL,
  submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status ENUM('Pending','Marked','Rejected') NOT NULL DEFAULT 'Pending',
  marked_by_user_id INT NULL,
  marked_at DATETIME NULL,
  feedback TEXT NULL,
  resubmission_count INT NOT NULL DEFAULT 0,
  CONSTRAINT fk_sub_activity FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
  CONSTRAINT fk_sub_group FOREIGN KEY (group_code) REFERENCES groups(group_code) ON DELETE CASCADE,
  CONSTRAINT fk_sub_student FOREIGN KEY (submitted_by_student_id) REFERENCES students_master(student_id) ON DELETE RESTRICT,
  CONSTRAINT fk_sub_marker FOREIGN KEY (marked_by_user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- TITLE WINDOW
CREATE TABLE IF NOT EXISTS title_selection_windows (
  id INT AUTO_INCREMENT PRIMARY KEY,
  is_open TINYINT(1) NOT NULL DEFAULT 0,
  scope_all_groups TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by INT NULL,
  CONSTRAINT fk_tsw_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- TITLE PROPOSALS
CREATE TABLE IF NOT EXISTS title_proposals (
  id INT AUTO_INCREMENT PRIMARY KEY,
  group_code VARCHAR(20) NOT NULL,
  title VARCHAR(255) NOT NULL,
  project_type VARCHAR(80) NULL,
  submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status_admin ENUM('Pending','Approved','Rejected') NOT NULL DEFAULT 'Pending',
  status_supervisor ENUM('Pending','Approved','Rejected') NOT NULL DEFAULT 'Pending',
  last_action_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_tp_group FOREIGN KEY (group_code) REFERENCES groups(group_code) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ARCHIVED TITLES
CREATE TABLE IF NOT EXISTS titles_archive (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  project_type VARCHAR(80) NULL,
  year VARCHAR(10) NULL,
  department VARCHAR(120) NULL,
  imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS=1;
