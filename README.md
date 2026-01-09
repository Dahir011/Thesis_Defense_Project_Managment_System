# UPMS+ TeamUp (Flask + MySQL/XAMPP + HTML/CSS/JS)

This project is a production-ready starter for **UPMS+ TeamUp**:
- Student / Supervisor / Admin portals
- Official student dataset import (CSV/Excel)
- Student account creation (2-step verification)
- TeamUp requests + automatic group creation
- Admin assigns supervisor to groups
- Admin/Supervisor create activities
- Students submit (PDF required when configured)
- Mark / Reject submissions
- Title selection window + approvals (Student → Admin → Supervisor)
- Accounts management

---

## 1) Requirements

- Python 3.10+
- XAMPP (MySQL)
- (Optional) phpMyAdmin

---

## 2) Setup (Windows + PowerShell)

### A) Create DB + tables (MySQL)

1. Start **XAMPP** → start **Apache** and **MySQL**
2. Open phpMyAdmin → **Import** → import `schema.sql`
   - OR run the SQL in phpMyAdmin SQL tab

### B) Configure environment

1. Copy `.env.example` to `.env`
2. Edit DB values if needed:
   - DB_NAME should match the DB you created (`upms_teamup`)
   - XAMPP default: user `root` and blank password

### C) Install Python dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### D) Create default admin + demo data (recommended)

```bash
flask --app run.py seed
```

This seeds:
- Admin: `admin / admin123`
- Supervisor: `SUP1001 / sup123`
- Students in dataset: `CS001`, `CS002`, `CS003`

### E) Run the server

```bash
python run.py
```

Open:
- Home: http://127.0.0.1:5000/
- Student login: /auth/student/login
- Supervisor login: /auth/supervisor/login
- Admin login: /auth/admin/login

---

## 3) Import Official Students Dataset

Admin → **Import Data**
- Upload CSV/Excel with columns:
  `student_id,name,gender,phone,faculty,program,batch`

After importing, students can create accounts:
Home → **Create Student Account**

---

## 4) How TeamUp Works

- Student A sends request to Student B (both must be registered & not in a group)
- Student B accepts → system creates group code automatically and adds both members
- Admin can add a 3rd student from **Registration → Add 3rd Student**

---

## 5) Notes

- Uploads are stored inside `uploads/`
- If you want to reset your DB, drop the database and re-import `schema.sql`.

---
