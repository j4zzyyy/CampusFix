# CampusFix — Smart Campus Complaint Management Prototype

A full-stack, presentation-ready prototype built with Flask, SQLite, HTML, CSS and JavaScript.

## Features
- Student, admin and department staff demo accounts
- Complaint creation with optional image upload
- Unique complaint ticket IDs
- Rule-based priority suggestion (Critical / High / Medium / Low)
- Automatic department routing by complaint category
- Possible duplicate report detection (token similarity)
- Complaint lifecycle tracking and staff/admin updates
- Student feedback after resolution
- Admin analytics dashboard with category chart
- Responsive UI for laptop and mobile

## Run locally

### 1. Install Python
Use Python 3.10 or newer.

### 2. Create and activate a virtual environment (recommended)
Windows:
```bash
python -m venv .venv
.venv\\Scripts\\activate
```
macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the app
```bash
python app.py
```
Open http://127.0.0.1:5000

The SQLite database and demo records are created automatically on first run.

## Demo logins

| Role | Email | Password |
|---|---|---|
| Student | student@campusfix.demo | student123 |
| Admin | admin@campusfix.demo | admin123 |
| Electrical staff | electrical@campusfix.demo | team123 |

## Suggested live demo flow (4–5 minutes)
1. Sign in as the student.
2. Open **New complaint**, report an issue such as “Projector not working” at “Seminar Hall”.
3. Show the generated ticket ID and the student complaint list.
4. Sign out and sign in as admin.
5. Open the new report, change the status to **In Progress**, assign a department and save an update note.
6. Sign back in as student and show the updated progress.
7. For the final step, sign in as admin and show the category analytics.

## Important prototype notes
- This is a local demonstration prototype, not a production deployment.
- The “smart” categorization, priority and duplicate detection are transparent rule-based demo logic, not a trained AI model.
- Before real deployment: set a strong `CAMPUSFIX_SECRET`, disable Flask debug mode, use HTTPS, add CSRF protection, configure production hosting, validate uploads more deeply, and review privacy/access controls with the institution.
- Demo data is fictional. Replace it with institution-approved data only after authorization.
