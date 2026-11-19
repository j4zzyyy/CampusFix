import os, sqlite3, uuid, re
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "campusfix.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("CAMPUSFIX_SECRET", "change-this-demo-secret-before-deployment")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

CATEGORIES = ["Electrical", "Plumbing", "Cleanliness", "Furniture", "Network / IT", "Other"]
DEPARTMENTS = ["Electrical", "Maintenance", "Housekeeping", "IT Support", "General"]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, role TEXT NOT NULL, department TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS complaints(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ticket TEXT UNIQUE NOT NULL,
            student_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
            category TEXT NOT NULL, location TEXT NOT NULL, photo TEXT, priority TEXT NOT NULL,
            department TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Submitted',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, resolution_note TEXT DEFAULT '',
            FOREIGN KEY(student_id) REFERENCES users(id))""")
        con.execute("""CREATE TABLE IF NOT EXISTS feedback(
            id INTEGER PRIMARY KEY AUTOINCREMENT, complaint_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL, rating INTEGER NOT NULL, comment TEXT DEFAULT '',
            created_at TEXT NOT NULL, UNIQUE(complaint_id, student_id))""")
        count = con.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        if count == 0:
            con.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                ("Aarav Student", "student@campusfix.demo", generate_password_hash("student123"), "student"))
            con.execute("INSERT INTO users(name,email,password,role,department) VALUES(?,?,?,?,?)",
                ("Admin User", "admin@campusfix.demo", generate_password_hash("admin123"), "admin", "General"))
            con.execute("INSERT INTO users(name,email,password,role,department) VALUES(?,?,?,?,?)",
                ("Electrical Team", "electrical@campusfix.demo", generate_password_hash("team123"), "staff", "Electrical"))
            student_id = con.execute("SELECT id FROM users WHERE email='student@campusfix.demo'").fetchone()["id"]
            now = datetime.now()
            samples = [
                ("CFX-1001", "Ceiling fan not working", "The fan in Room B-204 is not running.", "Electrical", "Block B · Room 204", "High", "Electrical", "Assigned", 3),
                ("CFX-1002", "Water dispenser issue", "Water dispenser near the library is leaking.", "Plumbing", "Central Library", "Medium", "Maintenance", "In Progress", 1),
                ("CFX-1003", "Wi-Fi connection unavailable", "The network is not available in the computer lab.", "Network / IT", "Computer Lab 2", "High", "IT Support", "Submitted", 0),
            ]
            for ticket,title,desc,cat,loc,priority,dept,status,days in samples:
                created = (now - timedelta(days=days)).isoformat(timespec="minutes")
                con.execute("""INSERT INTO complaints(ticket,student_id,title,description,category,location,priority,department,status,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (ticket, student_id, title, desc, cat, loc, priority, dept, status, created, created))

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                flash("You do not have permission to access that page.", "error")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return deco

def department_for(category):
    return {
        "Electrical": "Electrical", "Plumbing": "Maintenance",
        "Cleanliness": "Housekeeping", "Furniture": "Maintenance",
        "Network / IT": "IT Support", "Other": "General"
    }.get(category, "General")

def predict_priority(category, description, location):
    text = (description + " " + location).lower()
    urgent_terms = ["sparking", "smoke", "exposed wire", "short circuit", "flood", "electrical shock", "fire"]
    if any(term in text for term in urgent_terms):
        return "Critical"
    if category in ("Electrical", "Plumbing") or any(term in text for term in ["not working", "leak", "broken", "unsafe"]):
        return "High"
    if category in ("Network / IT", "Furniture"):
        return "Medium"
    return "Low"

def normalize(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower())) - {"the","and","is","in","at","a","to","of","for","not"}

def find_possible_duplicate(title, description, location):
    incoming = normalize(title + " " + description + " " + location)
    if not incoming:
        return None
    with db() as con:
        rows = con.execute("""SELECT ticket,title,description,location,status FROM complaints
            WHERE status NOT IN ('Resolved','Closed') ORDER BY id DESC LIMIT 100""").fetchall()
    best, best_score = None, 0
    for row in rows:
        existing = normalize(row["title"] + " " + row["description"] + " " + row["location"])
        score = len(incoming & existing) / max(1, len(incoming | existing))
        if score > best_score:
            best, best_score = row, score
    return dict(best) if best and best_score >= 0.42 else None

@app.context_processor
def inject_globals():
    return {"categories": CATEGORIES, "departments": DEPARTMENTS}

@app.route("/")
def home():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], role=user["role"], department=user["department"])
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as con:
        if session["role"] == "student":
            rows = con.execute("""SELECT c.*, u.name student_name FROM complaints c JOIN users u ON u.id=c.student_id
                WHERE c.student_id=? ORDER BY c.id DESC""", (session["user_id"],)).fetchall()
            counts = con.execute("""SELECT COUNT(*) total,
                SUM(status IN ('Submitted','Assigned')) open_count,
                SUM(status='In Progress') progress_count, SUM(status IN ('Resolved','Closed')) resolved_count
                FROM complaints WHERE student_id=?""", (session["user_id"],)).fetchone()
        else:
            rows = con.execute("""SELECT c.*, u.name student_name FROM complaints c JOIN users u ON u.id=c.student_id
                ORDER BY CASE priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, c.id DESC""").fetchall()
            counts = con.execute("""SELECT COUNT(*) total,
                SUM(status IN ('Submitted','Assigned')) open_count,
                SUM(status='In Progress') progress_count, SUM(status IN ('Resolved','Closed')) resolved_count
                FROM complaints""").fetchone()
    return render_template("dashboard.html", complaints=rows, counts=counts)

@app.route("/new", methods=["GET", "POST"])
@login_required
@role_required("student")
def new_complaint():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "Other")
        location = request.form.get("location", "").strip()
        if not title or not description or not location or category not in CATEGORIES:
            flash("Please complete all required fields.", "error")
            return render_template("new_complaint.html")
        duplicate = find_possible_duplicate(title, description, location)
        if duplicate:
            flash(f"Possible duplicate found: {duplicate['ticket']} — {duplicate['title']}. Your report was still saved for review.", "warning")
        photo_name = None
        photo = request.files.get("photo")
        if photo and photo.filename:
            ext = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else ""
            if ext not in ALLOWED_EXTENSIONS:
                flash("Upload a JPG, PNG or WEBP image (max 5 MB).", "error")
                return render_template("new_complaint.html")
            photo_name = uuid.uuid4().hex + "." + ext
            photo.save(os.path.join(UPLOAD_DIR, photo_name))
        priority = predict_priority(category, description, location)
        department = department_for(category)
        now = datetime.now().isoformat(timespec="minutes")
        ticket = "CFX-" + uuid.uuid4().hex[:6].upper()
        with db() as con:
            con.execute("""INSERT INTO complaints(ticket,student_id,title,description,category,location,photo,priority,department,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,'Submitted',?,?)""",
                (ticket, session["user_id"], title, description, category, location, photo_name, priority, department, now, now))
        flash(f"Complaint submitted successfully. Your ticket ID is {ticket}.", "success")
        return redirect(url_for("dashboard"))
    return render_template("new_complaint.html")

@app.route("/complaint/<int:complaint_id>")
@login_required
def complaint_detail(complaint_id):
    with db() as con:
        complaint = con.execute("""SELECT c.*,u.name student_name,u.email student_email FROM complaints c
            JOIN users u ON u.id=c.student_id WHERE c.id=?""", (complaint_id,)).fetchone()
        feedback = con.execute("SELECT * FROM feedback WHERE complaint_id=?", (complaint_id,)).fetchone()
    if not complaint or (session["role"] == "student" and complaint["student_id"] != session["user_id"]):
        flash("Complaint not found.", "error")
        return redirect(url_for("dashboard"))
    return render_template("detail.html", c=complaint, feedback=feedback)

@app.route("/complaint/<int:complaint_id>/update", methods=["POST"])
@login_required
@role_required("admin", "staff")
def update_complaint(complaint_id):
    status = request.form.get("status")
    department = request.form.get("department")
    note = request.form.get("resolution_note", "").strip()
    valid_status = ["Submitted", "Assigned", "In Progress", "Resolved", "Closed"]
    if status not in valid_status or department not in DEPARTMENTS:
        flash("Invalid update.", "error")
        return redirect(url_for("complaint_detail", complaint_id=complaint_id))
    now = datetime.now().isoformat(timespec="minutes")
    with db() as con:
        con.execute("""UPDATE complaints SET status=?,department=?,resolution_note=?,updated_at=? WHERE id=?""",
            (status, department, note, now, complaint_id))
    flash("Complaint updated.", "success")
    return redirect(url_for("complaint_detail", complaint_id=complaint_id))

@app.route("/complaint/<int:complaint_id>/feedback", methods=["POST"])
@login_required
@role_required("student")
def add_feedback(complaint_id):
    rating = request.form.get("rating", type=int)
    comment = request.form.get("comment", "").strip()
    with db() as con:
        c = con.execute("SELECT * FROM complaints WHERE id=? AND student_id=?", (complaint_id, session["user_id"])).fetchone()
        if not c or c["status"] not in ("Resolved", "Closed") or rating not in (1,2,3,4,5):
            flash("Feedback is available after resolution.", "error")
        else:
            try:
                con.execute("INSERT INTO feedback(complaint_id,student_id,rating,comment,created_at) VALUES(?,?,?,?,?)",
                    (complaint_id, session["user_id"], rating, comment, datetime.now().isoformat(timespec="minutes")))
                flash("Thanks for your feedback!", "success")
            except sqlite3.IntegrityError:
                flash("Feedback has already been submitted.", "warning")
    return redirect(url_for("complaint_detail", complaint_id=complaint_id))

@app.route("/api/analytics")
@login_required
@role_required("admin", "staff")
def analytics():
    with db() as con:
        by_category = con.execute("SELECT category label,COUNT(*) value FROM complaints GROUP BY category ORDER BY value DESC").fetchall()
        by_status = con.execute("SELECT status label,COUNT(*) value FROM complaints GROUP BY status").fetchall()
        by_department = con.execute("SELECT department label,COUNT(*) value FROM complaints GROUP BY department ORDER BY value DESC").fetchall()
    return jsonify({"categories":[dict(x) for x in by_category],"statuses":[dict(x) for x in by_status],"departments":[dict(x) for x in by_department]})

@app.route("/uploads/<filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, secure_filename(filename))

@app.errorhandler(413)
def too_large(_):
    flash("Image is too large. Maximum size is 5 MB.", "error")
    return redirect(url_for("new_complaint"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
