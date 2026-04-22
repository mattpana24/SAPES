import os
import sqlite3

import sqlite3

conn = sqlite3.connect("sapes.db")
cursor = conn.cursor()


import hashlib
from io import BytesIO
from datetime import datetime, date

import glob
import joblib
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

def load_ai_model():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(base_dir, "models")

    pkl_files = glob.glob(os.path.join(model_dir, "*.pkl"))
    joblib_files = glob.glob(os.path.join(model_dir, "*.joblib"))
    model_files = pkl_files + joblib_files

    st.write("Model folder:", model_dir)
    st.write("Model files found:", model_files)

    if not model_files:
        st.error("No AI models found. Put your .pkl or .joblib files inside the models folder.")
        st.stop()

    return joblib.load(model_files[0])
    
model = load_ai_models()
    
if "user" not in st.session_state:
    st.session_state["user"] = None

if "biometric_verified" not in st.session_state:
    st.session_state["biometric_verified"] = False
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


# =========================================================
# APP CONFIG
# =========================================================
st.set_page_config(
    page_title="SAPES",
    layout="wide",
    initial_sidebar_state="collapsed"
)
DB_NAME = "sapes.db"


# =========================================================
# DATABASE
# =========================================================
def get_connection():
    db_backend = os.getenv("DB_BACKEND", "sqlite").lower()

    if db_backend == "sqlite":
        return sqlite3.connect(DB_NAME, check_same_thread=False)

    # Deployment-ready structure:
    # Later this section can be extended for PostgreSQL/MySQL
    # using psycopg2 or pymysql without changing the rest of SAPES.
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'lecturer',
            student_id TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            full_name TEXT,
            program TEXT,
            year_of_study TEXT,
            department TEXT,
            email TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            attendance REAL NOT NULL,
            quiz_avg REAL NOT NULL,
            assignment_avg REAL NOT NULL,
            midterm REAL NOT NULL,
            late_submissions INTEGER NOT NULL,
            prev_gpa REAL NOT NULL,
            risk_level TEXT NOT NULL,
            confidence REAL,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interventions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            note TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            added_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT UNIQUE NOT NULL,
            course_name TEXT NOT NULL,
            lecturer TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            course_code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            course_code TEXT NOT NULL,
            test_score REAL DEFAULT 0,
            assignment_score REAL DEFAULT 0,
            exam_score REAL DEFAULT 0,
            total_score REAL DEFAULT 0,
            grade TEXT,
            uploaded_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            course_code TEXT NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL,
            marked_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            accuracy REAL DEFAULT 0,
            precision_score REAL DEFAULT 0,
            recall_score REAL DEFAULT 0,
            f1_score REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """) 

    cursor.execute("PRAGMA table_info(users)")
    user_columns = [row[1] for row in cursor.fetchall()]
    if "status" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")

    conn.commit()
    conn.close()


# =========================================================
# AUDIT TRAIL
# =========================================================
def log_audit(actor, action, details=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_logs (actor, action, details)
        VALUES (?, ?, ?)
    """, (actor, action, details))
    conn.commit()
    conn.close()


def load_audit_logs():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM audit_logs
        ORDER BY id DESC
    """, conn)
    conn.close()
    return df


# =========================================================
# AUTH
# =========================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username, password, role="lecturer", student_id=None):
    username = username.strip()

    if not username or not password.strip():
        return False, "Username and password are required."

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO users (username, password, role, student_id) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), role, student_id)
        )
        conn.commit()
        conn.close()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username already exists."


def login_user(username, password, role):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, username, role, student_id, status
        FROM users
        WHERE username = ? AND password = ? AND role = ?
        """,
        (username.strip(), hash_password(password), role)
    )

    user = cursor.fetchone()
    conn.close()

    if user:
        if len(user) >= 5 and user[4] == "disabled":
            return False, "This account has been disabled."

        return True, {
            "id": user[0],
            "username": user[1],
            "role": user[2],
            "student_id": user[3]
        }
    return False, "Wrong username, password, or account type."


def set_user_status(user_id, new_status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET status = ?
        WHERE id = ?
    """, (status, user_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def reset_user_password(username, new_password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET password = ?
        WHERE username = ?
    """, (hash_password(new_password), username.strip()))
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed


# =========================================================
# ADMIN FUNCTIONS
# =========================================================

def load_all_users():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT id, username, role, student_id, status
        FROM users
        ORDER BY id DESC
    """, conn)
    conn.close()
    return df


def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()
    return deleted


def admin_reset_user_password(user_id, new_password):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET password = ?
        WHERE id = ?
    """, (hash_password(new_password), user_id))

    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()

    return updated


def update_user_role(user_id, new_role):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET role = ?
        WHERE id = ?
    """, (new_role, user_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


# =========================================================
# ROLE PROTECTION
# =========================================================
def require_staff():
    if st.session_state.get("role") not in ["lecturer", "advisor", "admin"]:
        st.error("Access denied. This section is for staff only.")
        st.stop()


# =========================================================
# STUDENT PROFILES
# =========================================================
def save_student_profile(student_id, full_name, program, year_of_study, department, email, phone):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM student_profiles
        WHERE student_id = ?
    """, (student_id,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE student_profiles
            SET full_name = ?, program = ?, year_of_study = ?, department = ?, email = ?, phone = ?
            WHERE student_id = ?
        """, (full_name, program, year_of_study, department, email, phone, student_id))
        action = "updated"
    else:
        cursor.execute("""
            INSERT INTO student_profiles
            (student_id, full_name, program, year_of_study, department, email, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (student_id, full_name, program, year_of_study, department, email, phone))
        action = "created"

    conn.commit()
    conn.close()
    return action


def load_student_profile(student_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT *
        FROM student_profiles
        WHERE student_id = ?
        LIMIT 1
    """, conn, params=(student_id,))
    conn.close()
    return df


def load_all_student_profiles():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT *
        FROM student_profiles
        ORDER BY full_name ASC, student_id ASC
    """, conn)
    conn.close()
    return df


def get_student_contact_info(student_id):
    profile_df = load_student_profile(student_id)
    if profile_df.empty:
        return None

    row = profile_df.iloc[0]
    return {
        "student_id": row.get("student_id", ""),
        "full_name": row.get("full_name", ""),
        "email": row.get("email", ""),
        "phone": row.get("phone", ""),
        "program": row.get("program", ""),
        "department": row.get("department", "")
    }


def generate_email_message(student_id, title, message):
    contact = get_student_contact_info(student_id)

    if not contact:
        return {
            "to": "",
            "subject": title,
            "body": f"{message}"
        }

    student_name = contact["full_name"] if contact["full_name"] else student_id

    body = f"""
Dear {student_name},

{message}

Student ID: {student_id}
Program: {contact.get('program', '')}
Department: {contact.get('department', '')}

Regards,
SAPES Academic Support System
""".strip()

    return {
        "to": contact.get("email", ""),
        "subject": title,
        "body": body
    }


# =========================================================
# PREDICTION DATA
# =========================================================
def save_prediction(student_id, attendance, quiz, assignment, midterm, late, gpa, risk, confidence, user):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO predictions
        (student_id, attendance, quiz_avg, assignment_avg, midterm, late_submissions, prev_gpa, risk_level, confidence, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (student_id, attendance, quiz, assignment, midterm, late, gpa, risk, confidence, user))

    conn.commit()
    conn.close()


def load_data():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM predictions ORDER BY id DESC", conn)
    conn.close()
    return df


def delete_prediction(record_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM predictions WHERE id = ?", (record_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted > 0


def load_student_history(student_id):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM predictions WHERE student_id = ? ORDER BY id ASC",
        conn,
        params=(student_id,)
    )
    conn.close()
    return df


def get_latest_prediction_for_student(student_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT *
        FROM predictions
        WHERE student_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, conn, params=(student_id,))
    conn.close()

    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_latest_predictions_df():
    df = load_data()
    if df.empty:
        return df

    latest_df = (
        df.sort_values(by=["student_id", "id"], ascending=[True, False])
          .drop_duplicates(subset=["student_id"], keep="first")
          .sort_values(by="id", ascending=False)
          .reset_index(drop=True)
    )
    return latest_df


def apply_prediction_filters(df, selected_course=None, date_from=None, date_to=None):
    if df.empty:
        return df

    filtered_df = df.copy()

    if "created_at" in filtered_df.columns:
        filtered_df["created_at"] = pd.to_datetime(filtered_df["created_at"], errors="coerce")

    if selected_course and selected_course != "All":
        conn = get_connection()
        enrolled_students = pd.read_sql_query("""
            SELECT DISTINCT student_id
            FROM enrollments
            WHERE course_code = ?
        """, conn, params=(selected_course,))
        conn.close()

        if not enrolled_students.empty:
            allowed_students = enrolled_students["student_id"].astype(str).tolist()
            filtered_df = filtered_df[filtered_df["student_id"].astype(str).isin(allowed_students)]
        else:
            filtered_df = filtered_df.iloc[0:0]

    if date_from is not None and "created_at" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["created_at"] >= pd.to_datetime(date_from)]

    if date_to is not None and "created_at" in filtered_df.columns:
        end_date = pd.to_datetime(date_to) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        filtered_df = filtered_df[filtered_df["created_at"] <= end_date]

    return filtered_df


def global_search(query):
    conn = get_connection()

    users_df = pd.read_sql_query("""
        SELECT id, username, role, student_id
        FROM users
        WHERE username LIKE ? OR student_id LIKE ?
        ORDER BY id DESC
    """, conn, params=(f"%{query}%", f"%{query}%"))

    profiles_df = pd.read_sql_query("""
        SELECT *
        FROM student_profiles
        WHERE student_id LIKE ? OR full_name LIKE ? OR program LIKE ? OR department LIKE ? OR email LIKE ?
        ORDER BY id DESC
    """, conn, params=(f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))

    courses_df = pd.read_sql_query("""
        SELECT *
        FROM courses
        WHERE course_code LIKE ? OR course_name LIKE ? OR lecturer LIKE ?
        ORDER BY id DESC
    """, conn, params=(f"%{query}%", f"%{query}%", f"%{query}%"))

    enrollments_df = pd.read_sql_query("""
        SELECT e.id, e.student_id, e.course_code, c.course_name, c.lecturer
        FROM enrollments e
        LEFT JOIN courses c ON e.course_code = c.course_code
        WHERE e.student_id LIKE ? OR e.course_code LIKE ?
        ORDER BY e.id DESC
    """, conn, params=(f"%{query}%", f"%{query}%"))

    predictions_df = pd.read_sql_query("""
        SELECT *
        FROM predictions
        WHERE student_id LIKE ? OR created_by LIKE ? OR risk_level LIKE ?
        ORDER BY id DESC
    """, conn, params=(f"%{query}%", f"%{query}%", f"%{query}%"))

    results_df = pd.read_sql_query("""
        SELECT *
        FROM results
        WHERE student_id LIKE ? OR course_code LIKE ? OR uploaded_by LIKE ?
        ORDER BY id DESC
    """, conn, params=(f"%{query}%", f"%{query}%", f"%{query}%"))

    audit_df = pd.read_sql_query("""
        SELECT *
        FROM audit_logs
        WHERE actor LIKE ? OR action LIKE ? OR details LIKE ?
        ORDER BY id DESC
    """, conn, params=(f"%{query}%", f"%{query}%", f"%{query}%"))

    conn.close()

    return {
        "Users": users_df,
        "Student Profiles": profiles_df,
        "Courses": courses_df,
        "Enrollments": enrollments_df,
        "Predictions": predictions_df,
        "Results": results_df,
        "Audit Logs": audit_df
    }


# =========================================================
# INTERVENTIONS
# =========================================================
def add_intervention(student_id, note, status, user):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO interventions (student_id, note, status, added_by)
        VALUES (?, ?, ?, ?)
    """, (student_id, note, status, user))
    conn.commit()
    conn.close()


def load_interventions(student_id):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM interventions WHERE student_id = ? ORDER BY id DESC",
        conn,
        params=(student_id,)
    )
    conn.close()
    return df


def update_intervention_status(intervention_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE interventions
        SET status = ?
        WHERE id = ?
    """, (status, intervention_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


# =========================================================
# COURSES / RESULTS / NOTIFICATIONS
# =========================================================
def create_notification(student_id, title, message):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO notifications (student_id, title, message)
        VALUES (?, ?, ?)
    """, (student_id, title, message))
    conn.commit()
    conn.close()


def notification_exists(student_id, title, message):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM notifications
        WHERE student_id = ? AND title = ? AND message = ?
    """, (student_id, title, message))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def create_notification_if_new(student_id, title, message):
    if not notification_exists(student_id, title, message):
        create_notification(student_id, title, message)
        return True
    return False


def load_notifications(student_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM notifications
        WHERE student_id = ?
        ORDER BY id DESC
    """, conn, params=(student_id,))
    conn.close()
    return df


def load_notifications_for_staff_view():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT n.*, sp.full_name, sp.email, sp.phone
        FROM notifications n
        LEFT JOIN student_profiles sp ON n.student_id = sp.student_id
        ORDER BY n.id DESC
    """, conn)
    conn.close()
    return df


def mark_notification_read(notification_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()


def add_course(course_code, course_name, lecturer):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO courses (course_code, course_name, lecturer)
            VALUES (?, ?, ?)
        """, (course_code, course_name, lecturer))
        conn.commit()
        conn.close()
        return True, "Course added successfully."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Course code already exists."


def load_courses():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM courses ORDER BY course_code ASC", conn)
    conn.close()
    return df


def load_courses_by_lecturer(lecturer):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT *
        FROM courses
        WHERE lecturer = ?
        ORDER BY course_code ASC
    """, conn, params=(lecturer,))
    conn.close()
    return df


def enroll_student(student_id, course_code):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM enrollments WHERE student_id = ? AND course_code = ?
    """, (student_id, course_code))
    exists = cursor.fetchone()[0]

    if exists == 0:
        cursor.execute("""
            INSERT INTO enrollments (student_id, course_code)
            VALUES (?, ?)
        """, (student_id, course_code))
        conn.commit()

    conn.close()


def load_student_courses(student_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT e.id, e.student_id, e.course_code, c.course_name, c.lecturer
        FROM enrollments e
        LEFT JOIN courses c ON e.course_code = c.course_code
        WHERE e.student_id = ?
        ORDER BY e.id DESC
    """, conn, params=(student_id,))
    conn.close()
    return df


def load_students_by_course(course_code):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT e.student_id
        FROM enrollments e
        WHERE e.course_code = ?
        ORDER BY e.student_id ASC
    """, conn, params=(course_code,))
    conn.close()
    return df


def load_students_by_course_for_lecturer(course_code, lecturer):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT e.student_id
        FROM enrollments e
        INNER JOIN courses c ON e.course_code = c.course_code
        WHERE e.course_code = ? AND c.lecturer = ?
        ORDER BY e.student_id ASC
    """, conn, params=(course_code, lecturer))
    conn.close()
    return df


def save_result(student_id, course_code, test_score, assignment_score, exam_score, uploaded_by):
    total_score = float(test_score) + float(assignment_score) + float(exam_score)

    if total_score >= 80:
        grade = "A"
    elif total_score >= 70:
        grade = "B"
    elif total_score >= 60:
        grade = "C"
    elif total_score >= 50:
        grade = "D"
    else:
        grade = "F"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM results
        WHERE student_id = ? AND course_code = ?
        ORDER BY id DESC
        LIMIT 1
    """, (student_id, course_code))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE results
            SET test_score = ?,
                assignment_score = ?,
                exam_score = ?,
                total_score = ?,
                grade = ?,
                uploaded_by = ?,
                created_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            test_score,
            assignment_score,
            exam_score,
            total_score,
            grade,
            uploaded_by,
            existing[0]
        ))
        action = "updated"
    else:
        cursor.execute("""
            INSERT INTO results
            (student_id, course_code, test_score, assignment_score, exam_score, total_score, grade, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            student_id,
            course_code,
            test_score,
            assignment_score,
            exam_score,
            total_score,
            grade,
            uploaded_by
        ))
        action = "uploaded"

    conn.commit()
    conn.close()

    create_notification_if_new(
        student_id,
        "Result Update",
        f"Your result for {course_code} has been {action}. Grade: {grade}, Total: {total_score:.1f}"
    )

    return action, grade, total_score


def load_student_results(student_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM results
        WHERE student_id = ?
        ORDER BY id DESC
    """, conn, params=(student_id,))
    conn.close()
    return df


def load_results_for_lecturer(lecturer):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT r.id, r.student_id, r.course_code, r.test_score, r.assignment_score,
               r.exam_score, r.total_score, r.grade, r.uploaded_by, r.created_at
        FROM results r
        INNER JOIN courses c ON r.course_code = c.course_code
        WHERE c.lecturer = ?
        ORDER BY r.id DESC
    """, conn, params=(lecturer,))
    conn.close()
    return df


def update_result(result_id, test_score, assignment_score, exam_score, uploaded_by):
    total_score = float(test_score) + float(assignment_score) + float(exam_score)

    if total_score >= 80:
        grade = "A"
    elif total_score >= 70:
        grade = "B"
    elif total_score >= 60:
        grade = "C"
    elif total_score >= 50:
        grade = "D"
    else:
        grade = "F"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE results
        SET test_score = ?,
            assignment_score = ?,
            exam_score = ?,
            total_score = ?,
            grade = ?,
            uploaded_by = ?,
            created_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        test_score,
        assignment_score,
        exam_score,
        total_score,
        grade,
        uploaded_by,
        result_id
    ))

    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()

    return updated, grade, total_score


def delete_result(result_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM results WHERE id = ?", (result_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def generate_class_results_csv(course_code, lecturer):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT r.student_id, r.course_code, r.test_score, r.assignment_score,
               r.exam_score, r.total_score, r.grade, r.uploaded_by, r.created_at
        FROM results r
        INNER JOIN courses c ON r.course_code = c.course_code
        WHERE r.course_code = ? AND c.lecturer = ?
        ORDER BY r.student_id ASC
    """, conn, params=(course_code, lecturer))
    conn.close()
    return df.to_csv(index=False).encode("utf-8")


# =========================================================
# MODEL LOADING
# =========================================================
def load_model_safe(path):
    try:
        if os.path.exists(path):
            return joblib.load(path)
        return None
    except Exception as e:
        st.error(f"Error loading model from {path}: {e}")
        return None


# =========================================================
# HELPERS
# =========================================================
def get_recommendation(risk):
    if risk == "High":
        return [
            "Immediate academic intervention is required.",
            "Assign the student to an academic advisor.",
            "Provide tutoring and weekly progress monitoring.",
            "Engage the lecturer for targeted support.",
            "Review attendance and assignment behavior urgently."
        ]
    if risk == "Medium":
        return [
            "Monitor the student closely.",
            "Encourage regular attendance and timely submission of work.",
            "Provide mentorship and follow-up sessions.",
            "Track quiz and assignment performance weekly."
        ]
    return [
        "Student performance appears stable.",
        "Encourage consistency in attendance and coursework.",
        "Maintain regular academic support and motivation."
    ]


def get_simple_chatbot_response(user_prompt):
    prompt = user_prompt.lower().strip()

    if "high risk" in prompt:
        return "A high-risk student requires immediate academic intervention and close support."
    if "medium risk" in prompt:
        return "A medium-risk student should be monitored closely with mentoring and follow-up."
    if "low risk" in prompt:
        return "A low-risk student is relatively stable but should still be monitored for consistency."
    if "attendance" in prompt:
        return "Attendance is one of the strongest indicators of academic engagement and future performance."
    if "gpa" in prompt:
        return "Previous GPA reflects historical performance and can strongly influence risk prediction."
    if "recommend" in prompt:
        return "Recommendations in SAPES are based on risk level and are meant to support early intervention."
    return "I am the SAPES AI Assistant. I can explain risk levels, attendance, GPA, and recommendations."


def mark_attendance(student_id, course_code, date, status, user):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            course_code TEXT,
            date TEXT,
            status TEXT,
            marked_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        INSERT INTO attendance (student_id, course_code, date, status, marked_by)
        VALUES (?, ?, ?, ?, ?)
    """, (student_id, course_code, date, status, user))

    conn.commit()
    conn.close()
    return "saved"


def compute_attendance_percentage(student_id):
    df = load_attendance_by_student(student_id)

    if df.empty:
        return None

    total = len(df)
    present = len(df[df["status"] == "Present"])

    return round((present / total) * 100, 2)


def load_attendance_by_student(student_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM attendance
        WHERE student_id = ?
        ORDER BY date DESC
    """, conn, params=(student_id,))
    conn.close()
    return df


def load_attendance_by_course(course_code):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM attendance
        WHERE course_code = ?
        ORDER BY date DESC
    """, conn, params=(course_code,))
    conn.close()
    return df

def generate_pdf(student_id, risk, confidence, model_used, recommendations):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    content = []

    content.append(Paragraph("SAPES AI REPORT", styles["Title"]))
    content.append(Spacer(1, 12))
    content.append(Paragraph(f"Student ID: {student_id}", styles["Normal"]))
    content.append(Paragraph(f"Predicted Risk Level: {risk}", styles["Normal"]))
    content.append(Paragraph(f"Confidence Score: {confidence:.2f}%", styles["Normal"]))
    content.append(Paragraph(f"Model Used: {model_used}", styles["Normal"]))
    content.append(Spacer(1, 12))
    content.append(Paragraph("Recommendations:", styles["Heading2"]))

    for rec in recommendations:
        content.append(Paragraph(f"• {rec}", styles["Normal"]))

    doc.build(content)
    buffer.seek(0)
    return buffer


def generate_student_case_profile_pdf(student_id):
    profile_df = load_student_profile(student_id)
    history_df = load_student_history(student_id)
    interventions_df = load_interventions(student_id)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    content = []

    content.append(Paragraph("SAPES STUDENT CASE REPORT", styles["Title"]))
    content.append(Spacer(1, 12))
    content.append(Paragraph(f"Student ID: {student_id}", styles["Normal"]))
    content.append(Spacer(1, 12))

    if not profile_df.empty:
        row = profile_df.iloc[0]
        content.append(Paragraph("Student Details", styles["Heading2"]))
        content.append(Paragraph(f"Full Name: {row.get('full_name', '')}", styles["Normal"]))
        content.append(Paragraph(f"Program: {row.get('program', '')}", styles["Normal"]))
        content.append(Paragraph(f"Year of Study: {row.get('year_of_study', '')}", styles["Normal"]))
        content.append(Paragraph(f"Department: {row.get('department', '')}", styles["Normal"]))
        content.append(Paragraph(f"Email: {row.get('email', '')}", styles["Normal"]))
        content.append(Paragraph(f"Phone: {row.get('phone', '')}", styles["Normal"]))
        content.append(Spacer(1, 12))

    if not history_df.empty:
        latest = history_df.iloc[-1]
        content.append(Paragraph("Latest Prediction", styles["Heading2"]))
        content.append(Paragraph(f"Risk Level: {latest['risk_level']}", styles["Normal"]))
        content.append(Paragraph(f"Confidence: {latest['confidence']:.2f}%", styles["Normal"]))
        content.append(Paragraph(f"Attendance: {latest['attendance']}", styles["Normal"]))
        content.append(Paragraph(f"Quiz Average: {latest['quiz_avg']}", styles["Normal"]))
        content.append(Paragraph(f"Assignment Average: {latest['assignment_avg']}", styles["Normal"]))
        content.append(Paragraph(f"Midterm: {latest['midterm']}", styles["Normal"]))
        content.append(Paragraph(f"Previous GPA: {latest['prev_gpa']}", styles["Normal"]))
        content.append(Spacer(1, 12))

    if not interventions_df.empty:
        content.append(Paragraph("Intervention Notes", styles["Heading2"]))
        for _, row in interventions_df.iterrows():
            content.append(Paragraph(
                f"- {row['note']} | Status: {row.get('status', 'Pending')} | By: {row['added_by']} | Date: {row['created_at']}",
                styles["Normal"]
            ))

    doc.build(content)
    buffer.seek(0)
    return buffer


def risk_to_score(risk):
    mapping = {"Low": 1, "Medium": 2, "High": 3}
    return mapping.get(risk, 0)


def predict_risk_and_confidence(model_choice, attendance, quiz, assignment, midterm, late, gpa):
    data = pd.DataFrame([{
        "attendance": attendance,
        "quiz_avg": quiz,
        "assignment_avg": assignment,
        "midterm": midterm,
        "late_submissions": late,
        "prev_gpa": gpa
    }])

    risk = None
    confidence = 0.0

    if model_choice == "Random Forest" and rf_model is not None:
        risk = rf_model.predict(data)[0]
        if hasattr(rf_model, "predict_proba"):
            proba = rf_model.predict_proba(data)[0]
            confidence = float(max(proba) * 100)

    elif model_choice == "Logistic Regression" and lr_model is not None:
        risk = lr_model.predict(data)[0]
        if hasattr(lr_model, "predict_proba"):
            proba = lr_model.predict_proba(data)[0]
            confidence = float(max(proba) * 100)

    return risk, confidence, data


def get_top_at_risk_students(limit=5):
    df = get_latest_predictions_df()

    if df.empty:
        return df

    df = df[df["risk_level"].isin(["High", "Medium"])].copy()
    df = df.sort_values(by=["risk_level", "confidence"], ascending=[False, False])

    return df.head(limit)


def get_risk_distribution_by_course():
    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT e.course_code, p.risk_level, COUNT(*) as count
        FROM predictions p
        LEFT JOIN enrollments e ON p.student_id = e.student_id
        GROUP BY e.course_code, p.risk_level
        ORDER BY e.course_code
    """, conn)

    conn.close()
    return df


def show_front_page():
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(29,78,216,0.92), rgba(16,185,129,0.88));
        border-radius: 24px;
        padding: 40px 32px;
        text-align: center;
        box-shadow: 0 16px 40px rgba(0,0,0,0.25);
        margin-bottom: 24px;
    ">
        <h1 style="margin-bottom:10px;">🎓 Welcome to SAPES</h1>
        <h3 style="margin-top:0;">Student Academic Performance Early-Warning System</h3>
        <p style="max-width:800px; margin: 12px auto 0 auto; font-size: 1.05rem;">
            SAPES helps lecturers, academic advisors, and students monitor performance,
            predict academic risk early, manage courses, upload results, and receive support notifications.
        </p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
        <div class="portal-card center-text">
            <h3>📊 Predictive Analytics</h3>
            <p class="small-muted">Use AI models to identify students at risk early.</p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="portal-card center-text">
            <h3>📚 Courses & Results</h3>
            <p class="small-muted">Manage courses, upload results, and keep academic records organized.</p>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div class="portal-card center-text">
            <h3>🔔 Student Notifications</h3>
            <p class="small-muted">Automatically alert students about risk, results, and interventions.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### Why SAPES?")
    st.write("- Detects academic risk early using student indicators.")
    st.write("- Supports lecturers with recommendations and analytics.")
    st.write("- Gives students access to results, courses, and notifications.")
    st.write("- Improves follow-up through intervention notes and alerts.")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("🔐 Enter Portal", key="enter_portal_btn", use_container_width=True):
            st.session_state.show_portal = True
            st.rerun()

    with b2:
        if st.button("ℹ️ Learn More", key="learn_more_btn", use_container_width=True):
            st.info("SAPES is a smart academic support platform for risk prediction, intervention, course tracking, and student communication.")


def show_top_dashboard_bar(total_students, high_cases, total_preds):
    total_courses = len(load_courses_by_lecturer(st.session_state.user))

    t1, t2, t3, t4 = st.columns(4)

    with t1:
        st.markdown(f"""
        <div class="staff-panel">
            <p class="small-muted">Students</p>
            <p class="big-number">{total_students}</p>
        </div>
        """, unsafe_allow_html=True)

    with t2:
        st.markdown(f"""
        <div class="staff-panel">
            <p class="small-muted">High Risk</p>
            <p class="big-number">{high_cases}</p>
        </div>
        """, unsafe_allow_html=True)

    with t3:
        st.markdown(f"""
        <div class="staff-panel">
            <p class="small-muted">Courses</p>
            <p class="big-number">{total_courses}</p>
        </div>
        """, unsafe_allow_html=True)

    with t4:
        st.markdown(f"""
        <div class="staff-panel">
            <p class="small-muted">Predictions</p>
            <p class="big-number">{total_preds}</p>
        </div>
        """, unsafe_allow_html=True)


def require_admin():
    if st.session_state.get("role") != "admin":
        st.error("Only admin can access this section.")
        st.stop()


def load_all_users():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT id, username, role, student_id
        FROM users
        ORDER BY id DESC
    """, conn)
    conn.close()
    return df


def get_system_summary():
    conn = get_connection()

    users_count = pd.read_sql_query("SELECT COUNT(*) AS total FROM users", conn).iloc[0]["total"]
    students_count = pd.read_sql_query("SELECT COUNT(*) AS total FROM users WHERE role = 'student'", conn).iloc[0]["total"]
    lecturers_count = pd.read_sql_query("SELECT COUNT(*) AS total FROM users WHERE role = 'lecturer'", conn).iloc[0]["total"]
    advisors_count = pd.read_sql_query("SELECT COUNT(*) AS total FROM users WHERE role = 'advisor'", conn).iloc[0]["total"]
    admins_count = pd.read_sql_query("SELECT COUNT(*) AS total FROM users WHERE role = 'admin'", conn).iloc[0]["total"]
    predictions_count = pd.read_sql_query("SELECT COUNT(*) AS total FROM predictions", conn).iloc[0]["total"]
    courses_count = pd.read_sql_query("SELECT COUNT(*) AS total FROM courses", conn).iloc[0]["total"]
    results_count = pd.read_sql_query("SELECT COUNT(*) AS total FROM results", conn).iloc[0]["total"]
    notifications_count = pd.read_sql_query("SELECT COUNT(*) AS total FROM notifications", conn).iloc[0]["total"]
    interventions_count = pd.read_sql_query("SELECT COUNT(*) AS total FROM interventions", conn).iloc[0]["total"]

    conn.close()

    return {
        "users": int(users_count),
        "students": int(students_count),
        "lecturers": int(lecturers_count),
        "advisors": int(advisors_count),
        "admins": int(admins_count),
        "predictions": int(predictions_count),
        "courses": int(courses_count),
        "results": int(results_count),
        "notifications": int(notifications_count),
        "interventions": int(interventions_count)
    }

def render_risk_badge(risk):
    if risk == "High":
        return '<span class="risk-badge-high">HIGH RISK</span>'
    elif risk == "Medium":
        return '<span class="risk-badge-medium">MEDIUM RISK</span>'
    return '<span class="risk-badge-low">LOW RISK</span>'

def set_staff_navigation(target_page: str):
    page_to_group = {
        "📊 Predict": "Academic Monitoring",
        "📁 History": "Academic Monitoring",
        "👤 Student Case Profile": "Academic Monitoring",
        "🧾 Student Details": "Academic Monitoring",
        "📈 Analytics": "Academic Monitoring",
        "🧪 What-if Simulator": "Academic Monitoring",
        "🤖 AI Assistant": "Student Support",
        "🛟 Interventions": "Student Support",
        "📨 Notification Center": "Student Support",
        "📚 Courses": "Courses & Results",
        "📝 Results Upload": "Courses & Results",
        "✏️ Results Manager": "Courses & Results",
        "📤 Reports": "Courses & Results",
        "🧾 Audit Trail": "System Information",
        "ℹ️ About SAPES": "System Information",
    }
    st.session_state.nav_group = page_to_group.get(target_page, "Academic Monitoring")
    st.session_state.menu_choice = target_page

# =========================================================
# ROLE HELPERS
# =========================================================
def is_staff_role():
    return st.session_state.get("role") in ["lecturer", "advisor", "admin"]


def require_staff_like():
    if not is_staff_role():
        st.error("Access denied.")
        st.stop()


def is_admin():
    return st.session_state.get("role") == "admin"


def is_advisor():
    return st.session_state.get("role") == "advisor"
 

def require_admin():
    if not is_admin():
        st.error("Only admin can access this section.")
        st.stop()


# =========================================================
# ATTENDANCE
# =========================================================
def mark_attendance(student_id, course_code, attendance_date, status, marked_by):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM attendance_records
        WHERE student_id = ? AND course_code = ? AND attendance_date = ?
    """, (student_id, course_code, attendance_date))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE attendance_records
            SET status = ?, marked_by = ?, created_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, marked_by, existing[0]))
        action = "updated"
    else:
        cursor.execute("""
            INSERT INTO attendance_records (student_id, course_code, attendance_date, status, marked_by)
            VALUES (?, ?, ?, ?, ?)
        """, (student_id, course_code, attendance_date, status, marked_by))
        action = "created"

    conn.commit()
    conn.close()
    return action


def load_attendance_by_student(student_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM attendance_records
        WHERE student_id = ?
        ORDER BY attendance_date DESC, id DESC
    """, conn, params=(student_id,))
    conn.close()
    return df


def load_attendance_by_course(course_code):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM attendance_records
        WHERE course_code = ?
        ORDER BY attendance_date DESC, id DESC
    """, conn, params=(course_code,))
    conn.close()
    return df


def compute_attendance_percentage(student_id):
    df = load_attendance_by_student(student_id)
    if df.empty:
        return None

    total = len(df)
    present = len(df[df["status"] == "Present"])
    return round((present / total) * 100, 2) if total > 0 else None


# =========================================================
# EXPLAINABLE AI
# =========================================================
def explain_prediction_inputs(attendance, quiz, assignment, midterm, late, gpa):
    factors = []

    if attendance < 50:
        factors.append(("Low attendance", 3))
    elif attendance < 70:
        factors.append(("Moderate attendance concern", 2))

    if gpa < 2.0:
        factors.append(("Low GPA", 3))
    elif gpa < 2.5:
        factors.append(("Moderate GPA concern", 2))

    if quiz < 50:
        factors.append(("Low quiz average", 2))
    elif quiz < 65:
        factors.append(("Moderate quiz concern", 1))

    if assignment < 50:
        factors.append(("Low assignment average", 2))
    elif assignment < 65:
        factors.append(("Moderate assignment concern", 1))

    if midterm < 50:
        factors.append(("Low midterm score", 2))
    elif midterm < 65:
        factors.append(("Moderate midterm concern", 1))

    if late >= 5:
        factors.append(("Frequent late submissions", 2))
    elif late >= 2:
        factors.append(("Some late submissions", 1))

    factors = sorted(factors, key=lambda x: x[1], reverse=True)
    return factors[:5]


def get_prediction_explanation_text(risk, factors):
    if not factors:
        return f"The system predicts {risk} risk based on the current academic profile."

    joined = ", ".join([f[0] for f in factors])
    return f"The predicted risk is mainly influenced by: {joined}."


# =========================================================
# IMPROVEMENT TRACKER
# =========================================================
def get_student_improvement_status(student_id):
    df = load_student_history(student_id)
    if df is None or len(df) < 2:
        return "Not enough data"

    previous = df.iloc[-2]
    latest = df.iloc[-1]

    prev_score = risk_to_score(previous["risk_level"])
    latest_score = risk_to_score(latest["risk_level"])

    if latest_score < prev_score:
        return "Improved"
    elif latest_score > prev_score:
        return "Worsened"
    return "No Change"


# =========================================================
# DASHBOARD INTELLIGENCE
# =========================================================
def get_top_at_risk_students(limit=5):
    latest_df = get_latest_predictions_df()
    if latest_df.empty:
        return latest_df

    ranked = latest_df.copy()
    ranked["risk_score"] = ranked["risk_level"].apply(risk_to_score)
    ranked = ranked.sort_values(by=["risk_score", "confidence"], ascending=[False, False])
    return ranked.head(limit)


def get_risk_distribution_by_course():
    latest_df = get_latest_predictions_df()
    if latest_df.empty:
        return pd.DataFrame()

    conn = get_connection()
    enrollments_df = pd.read_sql_query("""
        SELECT e.student_id, e.course_code
        FROM enrollments e
    """, conn)
    conn.close()

    merged = latest_df.merge(enrollments_df, on="student_id", how="left")
    if merged.empty:
        return pd.DataFrame()

    grouped = merged.groupby(["course_code", "risk_level"]).size().unstack(fill_value=0).reset_index()
    return grouped


# =========================================================
# SMART CHATBOT
# =========================================================
def get_context_aware_chatbot_response(user_prompt):
    prompt = user_prompt.lower().strip()

    if "high risk" in prompt:
        return "A high-risk student needs urgent academic support, close follow-up, and intervention."

    if "attendance" in prompt:
        return "Attendance is important because low attendance often reduces engagement and increases academic risk."

    if "gpa" in prompt:
        return "GPA shows previous academic strength, so a low GPA can increase the probability of being at risk."

    if "intervention" in prompt:
        return "Interventions help staff record support actions such as mentoring, follow-up, and academic advising."

    if "student" in prompt and "risk" in prompt:
        latest_df = get_latest_predictions_df()
        if latest_df.empty:
            return "There is no student prediction data yet."
        return "You can check the Student Case Profile or Interventions section to see each student's latest risk status."

    return "I am the SAPES assistant. I can explain risk, attendance, GPA, interventions, and how the system works."

# =========================================================
# INITIALIZE
# =========================================================
init_db()
rf_model = load_model_safe("models/random_forest_model.pkl")
lr_model = load_model_safe("models/logistic_regression_model.pkl")


# =========================================================
# SESSION
# =========================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "role" not in st.session_state:
    st.session_state.role = None
if "student_id" not in st.session_state:
    st.session_state.student_id = None
if "show_portal" not in st.session_state:
    st.session_state.show_portal = False
if "menu_choice" not in st.session_state:
    st.session_state.menu_choice = None
if "nav_group" not in st.session_state:
    st.session_state.nav_group = "Academic Monitoring"


# =========================================================
# STYLING
# =========================================================
st.markdown("""
<style>
:root {
    --bg1: #081120;
    --bg2: #0f1c2e;
    --card: rgba(255,255,255,0.08);
    --card-strong: rgba(255,255,255,0.12);
    --border: rgba(255,255,255,0.14);
    --text: #f8fafc;
    --muted: #cbd5e1;
    --blue: #3b82f6;
    --cyan: #06b6d4;
    --green: #10b981;
    --yellow: #f59e0b;
    --red: #ef4444;
    --purple: #8b5cf6;
    --pink: #ec4899;
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(59,130,246,0.22), transparent 30%),
        radial-gradient(circle at top right, rgba(16,185,129,0.18), transparent 25%),
        linear-gradient(135deg, var(--bg1), var(--bg2));
}

html, body, [class*="css"] {
    font-family: 'Segoe UI', sans-serif;
}

h1, h2, h3, h4, h5, h6, p, label, div, span {
    color: var(--text) !important;
}

section[data-testid="stSidebar"] {
    background: rgba(5, 10, 20, 0.78);
    backdrop-filter: blur(14px);
    border-right: 1px solid var(--border);
}

section[data-testid="stSidebar"] * {
    color: var(--text) !important;
}

div[data-testid="stMetric"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 12px;
    backdrop-filter: blur(10px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.18);
}

div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    transition: 0.25s ease;
    background: var(--card-strong);
}

.stButton > button,
.stDownloadButton > button {
    border: none;
    border-radius: 12px;
    font-weight: 600;
    padding: 0.6rem 1rem;
    color: white !important;
    background: linear-gradient(90deg, var(--blue), var(--cyan));
    box-shadow: 0 8px 20px rgba(0,0,0,0.18);
}

.stButton > button:hover,
.stDownloadButton > button:hover {
    transform: translateY(-1px);
    transition: 0.2s ease;
    filter: brightness(1.05);
}

.portal-card,
.student-panel,
.staff-panel {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.18);
    backdrop-filter: blur(12px);
    margin-bottom: 18px;
}

.portal-card:hover,
.student-panel:hover,
.staff-panel:hover {
    background: var(--card-strong);
    transition: 0.25s ease;
}

.login-shell {
    max-width: 560px;
    margin: 30px auto;
}

.login-card {
    background: linear-gradient(135deg, rgba(139,92,246,0.35), rgba(59,130,246,0.30));
    border-radius: 24px;
    padding: 30px;
    box-shadow: 0 16px 40px rgba(0,0,0,0.24);
    border: 1px solid var(--border);
    backdrop-filter: blur(14px);
}

.student-banner {
    background: linear-gradient(90deg, rgba(16,185,129,0.9), rgba(34,197,94,0.78));
    border-radius: 22px;
    padding: 22px 26px;
    margin-bottom: 20px;
    box-shadow: 0 10px 28px rgba(0,0,0,0.22);
}

.staff-banner {
    background: linear-gradient(90deg, rgba(59,130,246,0.9), rgba(6,182,212,0.78));
    border-radius: 22px;
    padding: 22px 26px;
    margin-bottom: 20px;
    box-shadow: 0 10px 28px rgba(0,0,0,0.22);
}

.admin-banner {
    background: linear-gradient(90deg, rgba(139,92,246,0.95), rgba(236,72,153,0.82));
    border-radius: 22px;
    padding: 22px 26px;
    margin-bottom: 20px;
    box-shadow: 0 10px 28px rgba(0,0,0,0.22);
}

.advisor-banner {
    background: linear-gradient(90deg, rgba(245,158,11,0.95), rgba(249,115,22,0.82));
    border-radius: 22px;
    padding: 22px 26px;
    margin-bottom: 20px;
    box-shadow: 0 10px 28px rgba(0,0,0,0.22);
}

.small-muted {
    color: var(--muted) !important;
    font-size: 0.95rem;
}

.big-number {
    font-size: 1.95rem;
    font-weight: 800;
    margin: 0;
}

.center-text {
    text-align: center;
}

.section-title {
    font-size: 1.15rem;
    font-weight: 700;
    margin-bottom: 10px;
    padding-left: 8px;
    border-left: 4px solid var(--cyan);
}

.risk-badge-low {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(16,185,129,0.18);
    border: 1px solid rgba(16,185,129,0.35);
    color: #d1fae5 !important;
    font-weight: 700;
}

.risk-badge-medium {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(245,158,11,0.18);
    border: 1px solid rgba(245,158,11,0.35);
    color: #fde68a !important;
    font-weight: 700;
}

.risk-badge-high {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(239,68,68,0.18);
    border: 1px solid rgba(239,68,68,0.35);
    color: #fecaca !important;
    font-weight: 700;
}

div[data-testid="stDataFrame"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 8px;
}

div[data-testid="stExpander"] {
    border: 1px solid var(--border);
    border-radius: 16px;
    background: rgba(255,255,255,0.04);
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

.stTabs [data-baseweb="tab"] {
    background: rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 10px 16px;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(90deg, rgba(59,130,246,0.35), rgba(6,182,212,0.30)) !important;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# LOGIN / SIGNUP / FRONT PAGE
# =========================================================
if not st.session_state.logged_in and not st.session_state.show_portal:
    show_front_page()

elif not st.session_state.logged_in and st.session_state.show_portal:
    st.markdown("""
    <div class="login-shell">
        <div class="login-card">
            <h1 class="center-text" style="margin-bottom:8px;">🎓 SAPES</h1>
            <h3 class="center-text" style="margin-top:0;">Student Academic Performance Early-Warning System</h3>
            <p class="center-text small-muted">
                Smart academic monitoring, prediction, courses, results, and notifications in one platform.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("⬅ Back to Home", key="back_home_btn"):
        st.session_state.show_portal = False
        st.rerun()

    portal_menu = st.sidebar.selectbox("Portal Access", ["Login", "Sign Up", "Reset Password"])
    show_password = st.sidebar.checkbox("Show password", value=False)

    if portal_menu == "Login":
        st.markdown('<div class="portal-card">', unsafe_allow_html=True)
        st.subheader("🔐 Sign In")

        username = st.text_input("Username")
        password = st.text_input("Password", type="default" if show_password else "password")
        login_role = st.selectbox("Account Type", ["student", "lecturer", "advisor", "admin"])

        if st.button("Login", key="login_btn"):
            ok, result = login_user(username, password, login_role)
            if ok:
                user = result

                # 🚨 STATUS CHECK (NEW)
                if user.get("status", "active") != "active":
                    st.error("Your account is not active.")
                    st.stop()

                # 🔐 BIOMETRIC CHECK (ONLY FOR YOU)
                if user["username"].lower() == "matthew":
                    use_biometric = st.checkbox("Use biometric verification")

                    if use_biometric:
                        biometric_pin = st.text_input("Biometric PIN", type="password")
                    
                    
                        if biometric_pin == "2468":
                            st.session_state["biometric_verified"] = True
                        else:
                            st.error("Biometric verification failed.")
                            st.stop()
                    else:
                        st.session_state["biometric_verified"] = False

                st.session_state.logged_in = True
                st.session_state.user = user["username"]
                st.session_state.role = user["role"]
                st.session_state.student_id = user["student_id"]
                st.session_state.menu_choice = None
                if user["role"] == "student":
                    st.session_state.menu_choice = "📘 My Results"
                else:
                    st.session_state.nav_group = "Academic Monitoring"
                    st.session_state.menu_choice = "📊 Predict"
                st.rerun()
            else:
                st.error(result)
        st.markdown('</div>', unsafe_allow_html=True)

    elif portal_menu == "Sign Up":
        st.markdown('<div class="portal-card">', unsafe_allow_html=True)
        st.subheader("📝 Create Account")

        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="default" if show_password else "password")
        new_role = st.selectbox("Account Type", ["lecturer", "student", "advisor", "admin"])

        new_student_id = None
        if new_role == "student":
            new_student_id = st.text_input("Student ID")

        if st.button("Create Account", key="signup_btn"):
            ok, msg = register_user(new_username, new_password, new_role, new_student_id)
            if ok:
                st.success(msg)
                log_audit(new_username.strip(), "Account Created", f"Role: {new_role}, Student ID: {new_student_id}")
            else:
                st.error(msg)
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.markdown('<div class="portal-card">', unsafe_allow_html=True)
        st.subheader("♻️ Reset Password")

        reset_username = st.text_input("Username to Reset")
        new_reset_password = st.text_input("New Password", type="default" if show_password else "password", key="new_reset_password")

        if st.button("Reset Password", key="reset_password_btn"):
            if reset_username.strip() and new_reset_password.strip():
                changed = reset_user_password(reset_username.strip(), new_reset_password.strip())
                if changed:
                    st.success("Password reset successfully.")
                    log_audit(reset_username.strip(), "Password Reset", "Password was reset through reset flow.")
                else:
                    st.error("Username not found.")
            else:
                st.warning("Please fill in all fields.")
        st.markdown('</div>', unsafe_allow_html=True)


# =========================================================
# MAIN APP
# =========================================================
else:
    if st.session_state.role == "student":
        st.markdown(f"""
        <div class="student-banner">
            <h1 style="margin-bottom:6px;">🎓 Student Portal</h1>
            <p style="margin:0;">Welcome, {st.session_state.user} | Student ID: {st.session_state.student_id}</p>
        </div>
        """, unsafe_allow_html=True)

    elif st.session_state.role == "admin":
        st.markdown(f"""
        <div class="admin-banner">
            <h1 style="margin-bottom:6px;">👑 Admin Portal</h1>
            <p style="margin:0;">Welcome, {st.session_state.user} | System Control Center</p>
        </div>
        """, unsafe_allow_html=True)

    elif st.session_state.role == "advisor":
        st.markdown(f"""
        <div class="advisor-banner">
            <h1 style="margin-bottom:6px;">🧑‍🏫 Advisor Portal</h1>
            <p style="margin:0;">Welcome, {st.session_state.user} | Academic Support Oversight</p>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.markdown(f"""
        <div class="staff-banner">
            <h1 style="margin-bottom:6px;">📘 Lecturer Portal</h1>
            <p style="margin:0;">Welcome, {st.session_state.user}</p>
        </div>
        """, unsafe_allow_html=True)
    

    st.info("☰ Click the top-left icon to open/close the SAPES menu")

    st.sidebar.title("SAPES Menu")
    st.sidebar.write(f"Logged in as: **{st.session_state.role.title()}**")
    st.sidebar.write(f"User: **{st.session_state.user}**")
    st.sidebar.write(f"Date: **{datetime.now().strftime('%d %b %Y')}**")

    if st.session_state.role == "student" and st.session_state.student_id:
        st.sidebar.write(f"Student ID: **{st.session_state.student_id}**")

    st.sidebar.markdown("---")

    if st.session_state.role == "student":
        st.sidebar.markdown("### 🎓 Student Navigation")
        student_pages = [
            "📘 My Results",
            "🔔 My Notifications",
            "📚 My Courses",
            "👤 My Profile"
        ]
        default_student_index = 0
        if st.session_state.menu_choice in student_pages:
            default_student_index = student_pages.index(st.session_state.menu_choice)

        menu_choice = st.sidebar.radio(
            "Choose Section",
            student_pages,
            index=default_student_index
        )
        st.session_state.menu_choice = menu_choice

    else:
        st.sidebar.markdown("### 👨‍🏫 Staff Navigation")

        if st.session_state.role == "lecturer":
            nav_groups = [
                "Academic Monitoring",
                "Student Support",
                "Courses & Results",
                "System Information"
             ]
        elif st.session_state.role == "advisor":
             nav_groups = [
                 "Academic Monitoring",
                 "Student Support",
                "System Information"
             ]
        else:  # admin
             nav_groups = [
                 "Academic Monitoring",
                 "Student Support",
                 "Courses & Results",
                 "System Information",
                 "Administration"
             ]
        
        default_group_index = 0
        if st.session_state.nav_group in nav_groups:
            default_group_index = nav_groups.index(st.session_state.nav_group)

        nav_group = st.sidebar.selectbox(
            "Section Group",
            nav_groups,
            index=default_group_index
        )
        st.session_state.nav_group = nav_group

        if nav_group == "Academic Monitoring":
            staff_pages = [
                "📊 Predict",
                "📁 History",
                "👤 Student Case Profile",
                "📈 Analytics",
                "🧪 What-if Simulator"
            ]
        elif nav_group == "Student Support":
            staff_pages = [
                "🤖 AI Assistant",
                "🛟 Interventions",
                "📨 Notification Center"
            ]
        elif nav_group == "Courses & Results":
            if st.session_state.role == "lecturer" or st.session_state.role == "admin":
                staff_pages = [
                    "📚 Courses",
                    "📝 Results Upload",
                    "✏️ Results Manager",
                    "🗓 Attendance",
                    "📤 Reports"
               ]
            else:
               staff_pages = []

        elif nav_group == "Administration":
            staff_pages = [
                "👑 Admin Dashboard",
                "👥 User Management",
                "📨 Notification Center"
            ]

        else:
            if st.session_state.role == "System Information":
                staff_pages = [
                    "🧾 Audit Trail",
                    "ℹ️ About SAPES",
                    "📨 Notification Center"
            ]    
            else:
                staff_pages = [
                "🧾 Audit Trail",
                "ℹ️ About SAPES"
            ]

        default_staff_index = 0
        if st.session_state.menu_choice in staff_pages:
            default_staff_index = staff_pages.index(st.session_state.menu_choice)

        menu_choice = st.sidebar.radio(
            "Choose Page",
            staff_pages,
            index=default_staff_index
        )
        st.session_state.menu_choice = menu_choice

    st.sidebar.markdown("---")
    st.sidebar.info("Use the navigation above to move through the SAPES portal.")

    if st.sidebar.button("Logout", key="logout_btn"):
        log_audit(st.session_state.user, "Logout", "User logged out.")
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.role = None
        st.session_state.student_id = None
        st.session_state.menu_choice = None
        st.session_state.nav_group = "Academic Monitoring"
        st.rerun()

    # =====================================================
    # STUDENT DASHBOARD
    # =====================================================
    if st.session_state.role == "student":
        student_results = load_student_results(st.session_state.student_id)
        student_notifications = load_notifications(st.session_state.student_id)
        student_courses = load_student_courses(st.session_state.student_id)
        student_profile = load_student_profile(st.session_state.student_id)
        latest_prediction = get_latest_prediction_for_student(st.session_state.student_id)
        
        if latest_prediction:
            st.markdown('<div class="student-panel">', unsafe_allow_html=True)
            st.subheader("📊 Latest Academic Risk Status")
            st.markdown(render_risk_badge(latest_prediction.get("risk_level", "Low")), unsafe_allow_html=True)
            st.write(f"**Confidence Score:** {latest_prediction.get('confidence', 0):.2f}%")
            st.markdown('</div>', unsafe_allow_html=True)

        attendance_percentage = compute_attendance_percentage(st.session_state.student_id)
        if attendance_percentage is not None:
            st.markdown('<div class="student-panel">', unsafe_allow_html=True)
            st.subheader("🗓 Attendance Summary")
            st.write(f"**Attendance Percentage:** {attendance_percentage}%")

            student_attendance_df = load_attendance_by_student(st.session_state.student_id)
            if not student_attendance_df.empty:
                st.dataframe(student_attendance_df, use_container_width=True)

            st.markdown('</div>', unsafe_allow_html=True)
            
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="student-panel">
                <p class="small-muted">Results Uploaded</p>
                <p class="big-number">{len(student_results)}</p>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            unread_count = 0 if student_notifications.empty else int((student_notifications["is_read"] == 0).sum())
            st.markdown(f"""
            <div class="student-panel">
                <p class="small-muted">Unread Notifications</p>
                <p class="big-number">{unread_count}</p>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="student-panel">
                <p class="small-muted">Enrolled Courses</p>
                <p class="big-number">{len(student_courses)}</p>
            </div>
            """, unsafe_allow_html=True)

        if menu_choice == "📘 My Results":
            st.subheader("📘 My Results")
            if student_results.empty:
                st.info("No results uploaded yet.")
            else:
                st.dataframe(student_results, use_container_width=True)

        elif menu_choice == "🔔 My Notifications":
            st.subheader("🔔 My Notifications")
            if student_notifications.empty:
                st.info("No notifications yet.")
            else:
                st.dataframe(student_notifications, use_container_width=True)
                unread_df = student_notifications[student_notifications["is_read"] == 0]
                if not unread_df.empty:
                    notif_ids = unread_df["id"].tolist()
                    notif_to_mark = st.selectbox("Mark notification as read", notif_ids, key="notif_mark_select")
                    if st.button("Mark as Read", key="mark_notif_btn"):
                        mark_notification_read(int(notif_to_mark))
                        st.success("Notification marked as read.")
                        st.rerun()

        elif menu_choice == "📚 My Courses":
            st.subheader("📚 My Courses")
            if student_courses.empty:
                st.info("You are not enrolled in any courses yet.")
            else:
                st.dataframe(student_courses, use_container_width=True)

    

        elif menu_choice == "👤 My Profile":
            st.subheader("👤 My Profile")

            existing_profile = load_student_profile(st.session_state.student_id)

            full_name_val = ""
            program_val = ""
            year_val = ""
            department_val = ""
            email_val = ""
            phone_val = ""

            if not existing_profile.empty:
                row = existing_profile.iloc[0]
                full_name_val = row.get("full_name", "") or ""
                program_val = row.get("program", "") or ""
                year_val = row.get("year_of_study", "") or ""
                department_val = row.get("department", "") or ""
                email_val = row.get("email", "") or ""
                phone_val = row.get("phone", "") or ""

            st.markdown("### Update Your Personal Details")

            full_name = st.text_input("Full Name", value=full_name_val, key="student_profile_full_name")
            program = st.text_input("Program", value=program_val, key="student_profile_program")
            year_of_study = st.text_input("Year of Study", value=year_val, key="student_profile_year")
            department = st.text_input("Department", value=department_val, key="student_profile_department")
            email = st.text_input("Email", value=email_val, key="student_profile_email")
            phone = st.text_input("Phone", value=phone_val, key="student_profile_phone")

            if st.button("Save My Profile", key="student_save_profile_btn"):
                action = save_student_profile(
                    st.session_state.student_id,
                    full_name.strip(),
                    program.strip(),
                    year_of_study.strip(),
                    department.strip(),
                    email.strip(),
                    phone.strip()
                )

                log_audit(
                    st.session_state.user,
                    "Student Profile Self-Updated",
                    f"Student: {st.session_state.student_id}, Action: {action}"
                )

                st.success(f"Your profile has been {action} successfully.")
                st.rerun()

            st.markdown("### Current Saved Details")
            refreshed_profile = load_student_profile(st.session_state.student_id)
            if refreshed_profile.empty:
                st.info("No profile saved yet.")
            else:
                st.dataframe(refreshed_profile.drop(columns=["id"]), use_container_width=True)

            attendance_percentage = compute_attendance_percentage(st.session_state.student_id)

            if attendance_percentage is not None:
                st.markdown('<div class="student-panel">', unsafe_allow_html=True)
                st.subheader("🗓 Attendance Summary")
                st.write(f"**Attendence Percentage:** {attendance_percentage}%")

                student_attendance_df = load_attendance_by_student(st.session_state.student_id)

                if not student_attendance_df.empty:
                    st.dataframe(student_attendance_df, use_container_width=True)

                st.markdown('</div>', unsafe_allow_html=True)


    # =====================================================
    # STAFF DASHBOARD
    # =====================================================
    else:
        require_staff()

        latest_staff_data = get_latest_predictions_df()
        staff_data = load_data()

        total_preds = 0 if staff_data.empty else len(staff_data)
        total_students = 0 if latest_staff_data.empty else latest_staff_data["student_id"].nunique()
        high_cases = 0 if latest_staff_data.empty else int((latest_staff_data["risk_level"] == "High").sum())

        show_top_dashboard_bar(total_students, high_cases, total_preds)

        lecturer_courses_df = load_courses_by_lecturer(st.session_state.user)
        course_filter_options = ["All"]
        if not lecturer_courses_df.empty:
            course_filter_options.extend(lecturer_courses_df["course_code"].tolist())

        st.markdown("### Dashboard Filters")
        f1, f2, f3 = st.columns(3)

        with f1:
            selected_course_filter = st.selectbox(
                "Filter by Course",
                course_filter_options,
                key="dashboard_course_filter"
            )

        with f2:
            use_date_from = st.checkbox("Use Date From", key="use_date_from_filter")
            date_from_filter = st.date_input(
                "Date From",
                value=date.today(),
                key="dashboard_date_from"
            ) if use_date_from else None

        with f3:
            use_date_to = st.checkbox("Use Date To", key="use_date_to_filter")
            date_to_filter = st.date_input(
                "Date To",
                value=date.today(),
                key="dashboard_date_to"
            ) if use_date_to else None

        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button("🔍 Predict Student", use_container_width=True, key="top_predict_btn"):
                set_staff_navigation("📊 Predict")
                st.rerun()
        with a2:
            if st.button("📚 Upload Results", use_container_width=True, key="top_results_btn"):
                set_staff_navigation("📝 Results Upload")
                st.rerun()
        with a3:
            if st.button("🚨 View Alerts", use_container_width=True, key="top_alerts_btn"):
                set_staff_navigation("🛟 Interventions")
                st.rerun()

        with st.expander("🔎 Global Search", expanded=False):
            search_all_query = st.text_input("Search student ID, username, or course code", key="global_search_query")

            if search_all_query.strip():
                search_results = global_search(search_all_query.strip())

                for section_name, section_df in search_results.items():
                    st.markdown(f"### {section_name}")
                    if section_df.empty:
                        st.info(f"No {section_name.lower()} found.")
                    else:
                        st.dataframe(section_df, use_container_width=True)

        if menu_choice == "📊 Predict":
            st.subheader("📊 Enter Student Data")

            student_id = st.text_input("Student ID")
            attendance = st.slider("Attendance", 0, 100, 75)
            quiz = st.slider("Quiz Avg", 0, 100, 60)
            assignment = st.slider("Assignment Avg", 0, 100, 65)
            midterm = st.slider("Midterm", 0, 100, 55)
            late = st.number_input("Late Submissions", min_value=0, max_value=20, value=1, step=1)
            gpa = st.number_input("GPA", min_value=0.0, max_value=4.0, value=2.5, step=0.1)

            model_options = []
            if rf_model is not None:
                model_options.append("Random Forest")
            if lr_model is not None:
                model_options.append("Logistic Regression")

            if not model_options:
                st.error("No AI models found. Put your .pkl files inside the models folder.")
            else:
                model_choice = st.selectbox("Choose AI Model", model_options)

                if st.button("🔍 Predict Risk", key="predict_btn"):
                    if not student_id.strip():
                        st.warning("Please enter Student ID.")
                    else:
                        previous_latest = get_latest_prediction_for_student(student_id.strip())

                        risk, confidence, data = predict_risk_and_confidence(
                            model_choice, attendance, quiz, assignment, midterm, late, gpa
                        )

                        if risk == "High":
                            st.error(f"🚨 HIGH RISK: {risk}")
                        elif risk == "Medium":
                            st.warning(f"⚠️ MEDIUM RISK: {risk}")
                        else:
                            st.success(f"✅ LOW RISK: {risk}")

                        st.write(f"**Model Used:** {model_choice}")
                        st.write(f"**Confidence Score:** {confidence:.2f}%")

                        recommendations = get_recommendation(risk)
                        st.subheader("📌 Recommended Actions")
                        for rec in recommendations:
                            st.write(f"- {rec}")

                        st.subheader("🧠 Why This Prediction Was Made")

                        explanation_factors = explain_prediction_inputs(
                            attendance, quiz, assignment, midterm, late, gpa
                        )

                        if explanation_factors:
                            for factor, weight in explanation_factors:
                                st.write(f"- {factor}")
                        else:
                            st.write("- No strong negative factors detected.")

                        st.info(get_prediction_explanation_text(risk, explanation_factors))

                        pdf = generate_pdf(student_id, risk, confidence, model_choice, recommendations)
                        
                        save_prediction(
                            student_id.strip(),
                            attendance,
                            quiz,
                            assignment,
                            midterm,
                            late,
                            gpa,
                            risk,
                            confidence,
                            st.session_state.user
                        )
                        log_audit(
                            st.session_state.user,
                            "Prediction Saved",
                            f"Student: {student_id.strip()}, Risk: {risk}, Model: {model_choice}"
                        )

                        send_risk_notification = True
                        if previous_latest is not None and previous_latest["risk_level"] == risk:
                            send_risk_notification = False

                        if risk in ["High", "Medium"] and send_risk_notification:
                            if risk == "High":
                                notif_title = "High Academic Risk Alert"
                                notif_message = (
                                    "You have been identified as HIGH academic risk. "
                                    "Please contact your lecturer or academic advisor as soon as possible "
                                    "for support and intervention."
                                )
                            else:
                                notif_title = "Medium Academic Risk Alert"
                                notif_message = (
                                    "You have been identified as MEDIUM academic risk. "
                                    "Please improve attendance, coursework submission, and academic engagement."
                                )

                            create_notification_if_new(
                                student_id.strip(),
                                notif_title,
                                notif_message
                            )

                        if model_choice == "Random Forest" and hasattr(rf_model, "feature_importances_"):
                            st.subheader("📈 Feature Importance")
                            features = data.columns
                            importance = rf_model.feature_importances_

                            fig, ax = plt.subplots()
                            ax.barh(features, importance)
                            ax.set_xlabel("Importance")
                            ax.set_ylabel("Features")
                            ax.set_title("Random Forest Feature Importance")
                            st.pyplot(fig)

                        pdf = generate_pdf(student_id, risk, confidence, model_choice, recommendations)
                        st.download_button(
                            label="📄 Download PDF Report",
                            data=pdf,
                            file_name=f"sapes_report_{student_id}.pdf",
                            mime="application/pdf",
                            key="pdf_download_btn"
                        )

        elif menu_choice == "📁 History":
            st.subheader("📁 Prediction History")
            df = load_data()

            if df.empty:
                st.info("No saved prediction data.")
            else:
                df = apply_prediction_filters(
                    df,
                    selected_course=selected_course_filter,
                    date_from=date_from_filter,
                    date_to=date_to_filter
                )

                search = st.text_input("Search Student ID or Risk Level")

                if search:
                    df = df[
                        df["student_id"].astype(str).str.contains(search, case=False, na=False) |
                        df["risk_level"].astype(str).str.contains(search, case=False, na=False)
                    ]

                st.dataframe(df, use_container_width=True)

                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇ Download CSV", csv, "sapes_history.csv", "text/csv", key="csv_download_btn")

                st.subheader("🗑 Delete Record")
                record_id = st.number_input("Enter Record ID", min_value=1, step=1, key="delete_record_id")

                if st.button("Delete", key="delete_btn"):
                    deleted = delete_prediction(record_id)
                    if deleted:
                        log_audit(st.session_state.user, "Prediction Deleted", f"Prediction ID: {record_id}")
                        st.success("Deleted successfully.")
                        st.rerun()
                    else:
                        st.warning("Record ID not found.")

        elif menu_choice == "👤 Student Case Profile":
            st.subheader("👤 Student Case Profile")
            all_data = load_data()

            if all_data.empty:
                st.info("No student records yet.")
            else:
                student_ids = sorted(all_data["student_id"].dropna().astype(str).unique().tolist())
                selected_student = st.selectbox("Select Student ID", student_ids)

                if selected_student:
                    student_df = load_student_history(selected_student)
                    notes_df = load_interventions(selected_student)
                    profile_df = load_student_profile(selected_student)

                    if not profile_df.empty:
                        st.subheader("Student Details")
                        st.dataframe(profile_df.drop(columns=["id"]), use_container_width=True)

                    if student_df.empty:
                        st.warning("No records found for this student.")
                    else:
                        latest = student_df.iloc[-1]

                        c1, c2, c3 = st.columns(3)
                        c1.metric("Latest Risk", latest["risk_level"])
                        c2.metric("Latest Confidence", f"{latest['confidence']:.2f}%")
                        c3.metric("Total Predictions", len(student_df))

                        st.subheader("Latest Student Indicators")
                        latest_indicators = pd.DataFrame({
                            "Indicator": ["Attendance", "Quiz Avg", "Assignment Avg", "Midterm", "Late Submissions", "Previous GPA"],
                            "Value": [
                                latest["attendance"],
                                latest["quiz_avg"],
                                latest["assignment_avg"],
                                latest["midterm"],
                                latest["late_submissions"],
                                latest["prev_gpa"]
                            ]
                        })
                        st.dataframe(latest_indicators, use_container_width=True)

                        st.subheader("Prediction History")
                        st.dataframe(student_df, use_container_width=True)

                        st.subheader("Risk Trend")
                        trend_df = student_df.copy()
                        trend_df["risk_score"] = student_df["risk_level"].apply(risk_to_score)
                        trend_chart = trend_df[["id", "risk_score"]].set_index("id")
                        st.line_chart(trend_chart)

                        st.caption("Risk score: Low = 1, Medium = 2, High = 3")

                        st.subheader("Performance Trends")
                        trend_metrics = student_df[[
                            "attendance", "quiz_avg", "assignment_avg", "midterm", "prev_gpa"
                        ]].copy()
                        st.line_chart(trend_metrics)

                        st.subheader("Intervention Notes")
                        if notes_df.empty:
                            st.info("No intervention notes yet.")
                        else:
                            st.dataframe(
                                notes_df[["id", "note", "status", "added_by", "created_at"]],
                                use_container_width=True
                            )

                            intervention_ids = notes_df["id"].tolist()
                            selected_intervention_id = st.selectbox(
                                "Select Intervention ID to Update Status",
                                intervention_ids,
                                key="selected_intervention_id"
                            )
                            new_status = st.selectbox(
                                "New Status",
                                ["Pending", "In Progress", "Resolved"],
                                key="intervention_new_status"
                            )

                            if st.button("Update Intervention Status", key="update_intervention_status_btn"):
                                updated = update_intervention_status(selected_intervention_id, new_status)
                                if updated:
                                    log_audit(
                                        st.session_state.user,
                                        "Intervention Status Updated",
                                        f"Intervention ID: {selected_intervention_id}, Student: {selected_student}, Status: {new_status}"
                                    )
                                    create_notification_if_new(
                                        selected_student,
                                        "Intervention Status Update",
                                        f"An intervention note status has been updated to {new_status}."
                                    )
                                    st.success("Intervention status updated.")
                                    st.rerun()
                                else:
                                    st.warning("Update failed.")

                        st.subheader("Add Intervention Note")
                        note_text = st.text_area("Write note / action taken", key="intervention_note")
                        note_status = st.selectbox("Status", ["Pending", "In Progress", "Resolved"], key="new_intervention_status")

                        if st.button("Save Intervention Note", key="save_note_btn"):
                            if note_text.strip():
                                add_intervention(selected_student, note_text.strip(), note_status, st.session_state.user)
                                log_audit(
                                    st.session_state.user,
                                    "Intervention Added",
                                    f"Student: {selected_student}, Status: {note_status}, Note: {note_text.strip()}"
                                )
                                create_notification_if_new(
                                    selected_student,
                                    "New Intervention Note",
                                    f"A lecturer has added an intervention note with status {note_status} to support your academic progress."
                                )
                                st.success("Intervention note saved.")
                                st.rerun()
                            else:
                                st.warning("Please type a note first.")

        

            if st.button("Save Student Profile", key="save_student_profile_btn"):
                if student_id_profile.strip():
                    action = save_student_profile(
                        student_id_profile.strip(),
                        full_name.strip(),
                        program.strip(),
                        year_of_study.strip(),
                        department.strip(),
                        email.strip(),
                        phone.strip()
                    )
                    log_audit(
                        st.session_state.user,
                        "Student Profile Saved",
                        f"Student: {student_id_profile.strip()}, Action: {action}"
                    )
                    st.success(f"Student profile {action} successfully.")
                    st.rerun()
                else:
                    st.warning("Please enter Student ID.")

            st.markdown("### Existing Student Profiles")
            profiles_df = load_all_student_profiles()
            if profiles_df.empty:
                st.info("No student profiles yet.")
            else:
                st.dataframe(profiles_df, use_container_width=True)

        elif menu_choice == "📈 Analytics":
            st.markdown('<div class="staff-panel">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Analytics Dashboard</div>', unsafe_allow_html=True)

            latest_df = get_latest_predictions_df()
            latest_df = apply_prediction_filters(
                latest_df,
                selected_course=selected_course_filter,
                date_from=date_from_filter,
                date_to=date_to_filter
            )

            if latest_df.empty:
                st.info("No prediction data available yet.")
            else:
                total_records = len(load_data())
                total_students = latest_df["student_id"].nunique()
                high_risk_count = (latest_df["risk_level"] == "High").sum()
                medium_risk_count = (latest_df["risk_level"] == "Medium").sum()

                a1, a2, a3, a4 = st.columns(4)
                a1.metric("Total Predictions", total_records)
                a2.metric("Unique Students", total_students)
                a3.metric("High Risk Cases", int(high_risk_count))
                a4.metric("Medium Risk Cases", int(medium_risk_count))
 
                st.markdown('<div class="section-title">Latest Risk Distribution</div>', unsafe_allow_html=True)
                st.bar_chart(latest_df["risk_level"].value_counts())

                st.markdown('<div class="section-title">Predictions by User</div>', unsafe_allow_html=True)
                full_df = load_data()
                full_df = apply_prediction_filters(
                    full_df,
                    selected_course=selected_course_filter,
                    date_from=date_from_filter,
                    date_to=date_to_filter
                )
                if not full_df.empty:
                    st.bar_chart(full_df["created_by"].value_counts())
                else:
                    st.info("No user prediction data for the selected filters.")

                st.markdown('<div class="section-title">Average Student Indicators</div>', unsafe_allow_html=True)
                avg_data = latest_df[["attendance", "quiz_avg", "assignment_avg", "midterm", "prev_gpa"]].mean()
                st.bar_chart(avg_data)

                if "confidence" in latest_df.columns:
                    st.markdown('<div class="section-title">Average Confidence by Risk Level</div>', unsafe_allow_html=True)
                    confidence_by_risk = latest_df.groupby("risk_level")["confidence"].mean()
                    st.bar_chart(confidence_by_risk)

                st.markdown('<div class="section-title">Top At-Risk Students</div>', unsafe_allow_html=True)
                top_risk_df = get_top_at_risk_students(5)

                if top_risk_df.empty:
                    st.info("No at-risk students found.")
                else:
                    st.dataframe(
                        top_risk_df[["student_id", "risk_level", "confidence", "created_at"]],
                        use_container_width=True
                    )

                st.markdown('<div class="section-title">Risk Distribution by Course</div>', unsafe_allow_html=True)
                risk_by_course_df = get_risk_distribution_by_course()

                if risk_by_course_df.empty:
                    st.info("No course-level risk data available.")
                else:
                    st.dataframe(risk_by_course_df, use_container_width=True)

            st.markdown('</div>', unsafe_allow_html=True)
        
        elif menu_choice == "👥 User Management":
            require_admin()
            st.subheader("👥 User Management")

            users_df = load_all_users()

            if users_df.empty:
                st.info("No users found.")
            else:
                search_user = st.text_input("Search by Username, Role, or Student ID", key="admin_user_search")

                filtered_users = users_df.copy()

                if search_user.strip():
                    q = search_user.strip()
                    filtered_users = filtered_users[
                        filtered_users["username"].astype(str).str.contains(q, case=False, na=False) |
                        filtered_users["role"].astype(str).str.contains(q, case=False, na=False) |
                        filtered_users["student_id"].astype(str).str.contains(q, case=False, na=False)
                    ]

                st.dataframe(filtered_users, use_container_width=True)

                user_ids = filtered_users["id"].tolist()

                if user_ids:
                    selected_user_id = st.selectbox("Select User ID", user_ids, key="admin_selected_user")
                    selected_row = filtered_users[filtered_users["id"] == selected_user_id].iloc[0]
                    
                    st.markdown("### Selected User Details")
                    st.write(f"**Username:** {selected_row['username']}")
                    st.write(f"**Role:** {selected_row['role']}")
                    st.write(f"**Student ID:** {selected_row['student_id']}")
                    status = selected_row.get('status', 'active')

                    st.write(f"**Status:** {status}")

                    st.markdown("### 🔄 Update User Status")

                    new_status = st.selectbox(
                        "Change Status",
                        ["active", "inactive", "suspended"],
                        index=["active", "inactive", "suspended"].index(status) if status in ["active", "inactive", "suspended"] else 0
                    )

                    if st.button("Update Status"):
                        conn = sqlite3.connect("sapes.db")
                        cursor = conn.cursor()

                        cursor.execute(
                            "UPDATE users SET status = ? WHERE id = ?",
                            (new_status, selected_user_id)
                        )

                        conn.commit()
                        conn.close()

                    st.success("Status updated successfully ✅")

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.markdown("#### Reset User Password")

                        admin_new_password = st.text_input(
                            "New Password",
                            type="password",
                            key="admin_reset_password_input"
                        )

                        if st.button("Reset Selected User Password", key="admin_reset_password_btn"):
                            if admin_new_password.strip():
                                updated = admin_reset_user_password(selected_user_id, admin_new_password.strip())

                                if updated:
                                    log_audit(
                                        st.session_state.user,
                                        "Admin Password Reset",
                                        f"Target User ID: {selected_user_id}, Username: {selected_row['username']}"
                                    )
                                    st.success("Password reset successfully.")
                                else:
                                     st.error("Password reset failed.")
                            else:
                                 st.warning("Please enter a new password.")

                    with col2:
                        st.markdown("#### Delete User")

                        if st.button("Delete Selected User", key="admin_delete_user_btn"):
                             deleted = delete_user(selected_user_id)

                             if deleted:
                                 log_audit(
                                 st.session_state.user,
                                 "User Deleted",
                                 f"Target User ID: {selected_user_id}, Username: {selected_row['username']}"
                                 )

                                 st.success("User deleted successfully.")
                                 st.rerun()
                             else:
                                 st.error("User deletion failed.")
                    with col3:
                        st.markdown("#### Edit User Role")
                        new_role = st.selectbox(
                           "New Role",
                           ["student", "lecturer", "advisor", "admin"],
                           key="admin_edit_role_select"
                        )

                        if st.button("Update Selected User Role", key="admin_update_role_btn"):
                            if int(selected_user_id) == int(st.session_state.get("user_id", -1)) and new_role != "admin":
                                st.warning("You cannot remove your own admin role while logged in.")
                            else:
                                updated = update_user_role(selected_user_id, new_role)
                                if updated:
                                    log_audit(
                                        st.session_state.user,
                                        "User Role Updated",
                                       f"Target User ID: {selected_user_id}, Username: {selected_row['username']}, New Role: {new_role}"
                                    )
                                    st.success("User role updated successfully.")
                                    st.rerun()
                                else:
                                    st.error("Role update failed.")

                    with col4:
                        st.markdown("#### Disable / Enable Account")
                        current_status = selected_row.get("status", "active")

                        if current_status == "active":
                            button_label = "disable account"
                            next_status = "disabled"
                        else:
                            button_label = "enable account"
                            next_status = "aactive"
                        st.write(f"**current status:** {current_status}")   

                        if st.button(button_label, key="admin_toggle_status_btn"):
                            if int(selected_user_id) == int(st.session_state.get("user_id", -1)) and next_status == "disabled":

                                st.warning("you cannot disable your own logged-in admin.") 
                            else:
                                updated = set_user_status(selected_user_id, next_status)  
                                if updated:
                                    log_audit(
                                        st.session_state.user,
                                        "user status changed",
                                        f"user id: {selected_user_id}, new status: {next_status}"
                                    )         
                    
                                    st.success(f"Account is now {next_status}.")
                                    st.rerun()
                                else:
                                    st.error("Status update failed.")
             
  
        elif menu_choice == "🤖 AI Assistant":
            st.subheader("🤖 SAPES AI Assistant")
            user_prompt = st.text_input("Ask the assistant something")

            if st.button("Ask AI", key="ask_ai_btn"):
                if user_prompt.strip():
                    st.success(get_context_aware_chatbot_response(user_prompt))
                else:
                    st.warning("Please type a question first.")

        elif menu_choice == "🛟 Interventions":
            st.subheader("🛟 Interventions Dashboard")
            latest_df = get_latest_predictions_df()
            latest_df = apply_prediction_filters(
                latest_df,
                selected_course=selected_course_filter,
                date_from=date_from_filter,
                date_to=date_to_filter
            )

            if latest_df.empty:
                st.info("No prediction data available yet.")
            else:
                alerts_df = latest_df[latest_df["risk_level"].isin(["High", "Medium"])].copy()
                alerts_df = alerts_df.sort_values(by="id", ascending=False)

                high_risk_df = alerts_df[alerts_df["risk_level"] == "High"].copy()
                medium_risk_df = alerts_df[alerts_df["risk_level"] == "Medium"].copy()

                c1, c2 = st.columns(2)
                c1.metric("High Risk Students", len(high_risk_df))
                c2.metric("Medium Risk Students", len(medium_risk_df))

                st.markdown("### 🚨 Current High Risk Cases")
                if high_risk_df.empty:
                    st.success("No current high-risk students at the moment.")
                else:
                    st.dataframe(
                        high_risk_df[["student_id", "risk_level", "confidence", "created_by", "created_at"]],
                        use_container_width=True
                    )

                st.markdown("### ⚠️ Current Medium Risk Cases")
                if medium_risk_df.empty:
                    st.info("No current medium-risk students at the moment.")
                else:
                    st.dataframe(
                        medium_risk_df[["student_id", "risk_level", "confidence", "created_by", "created_at"]],
                        use_container_width=True
                    )

                st.markdown("### Quick Intervention Guide")
                st.write("- High risk: assign advisor, tutoring, weekly follow-up.")
                st.write("- Medium risk: closer monitoring, mentorship, coursework reminders.")
                st.write("- Low risk: encourage consistency and continued support.")

        elif menu_choice == "📨 Notification Center":
            require_staff()
            st.subheader("📨 Notification Center")

            notifications_df = load_notifications_for_staff_view()

            if notifications_df.empty:
                st.info("No notifications found.")
            else:
                st.dataframe(notifications_df, use_container_width=True)

                selected_student_for_message = st.text_input(
                    "Student ID for Email-Ready Message",
                    key="email_ready_student_id"
                )
                email_title = st.text_input(
                    "Message Title",
                    value="Academic Support Update",
                    key="email_ready_title"
                )
                email_body = st.text_area("Message Body", key="email_ready_body")

                if st.button("Generate Email-Ready Draft", key="generate_email_ready_btn"):
                    if selected_student_for_message.strip() and email_title.strip() and email_body.strip():
                        draft = generate_email_message(
                            selected_student_for_message.strip(),
                            email_title.strip(),
                            email_body.strip()
                        )

                        st.markdown("### Email Draft")
                        st.write(f"**To:** {draft['to']}")
                        st.write(f"**Subject:** {draft['subject']}")
                        st.text_area("Draft Body", draft["body"], height=220, key="email_ready_preview")

                        log_audit(
                            st.session_state.user,
                            "Email Draft Generated",
                            f"Student: {selected_student_for_message.strip()}, Title: {email_title.strip()}"
                        )
                    else:
                        st.warning("Please fill in student ID, title, and message body.")

        elif menu_choice == "🧪 What-if Simulator":
            st.subheader("🧪 What-if Simulator")
            st.write("Adjust student indicators and see how the predicted risk changes.")

            sim_attendance = st.slider("Simulated Attendance", 0, 100, 75, key="sim_attendance")
            sim_quiz = st.slider("Simulated Quiz Avg", 0, 100, 60, key="sim_quiz")
            sim_assignment = st.slider("Simulated Assignment Avg", 0, 100, 65, key="sim_assignment")
            sim_midterm = st.slider("Simulated Midterm", 0, 100, 55, key="sim_midterm")
            sim_late = st.number_input("Simulated Late Submissions", min_value=0, max_value=20, value=1, step=1, key="sim_late")
            sim_gpa = st.number_input("Simulated GPA", min_value=0.0, max_value=4.0, value=2.5, step=0.1, key="sim_gpa")

            sim_model_options = []
            if rf_model is not None:
                sim_model_options.append("Random Forest")
            if lr_model is not None:
                sim_model_options.append("Logistic Regression")

            if not sim_model_options:
                st.error("No AI models found.")
            else:
                sim_model_choice = st.selectbox("Choose Model for Simulation", sim_model_options, key="sim_model_choice")

                if st.button("Run Simulation", key="run_simulation_btn"):
                    sim_risk, sim_confidence, sim_data = predict_risk_and_confidence(
                        sim_model_choice,
                        sim_attendance,
                        sim_quiz,
                        sim_assignment,
                        sim_midterm,
                        sim_late,
                        sim_gpa
                    )

                    if sim_risk == "High":
                        st.error(f"🚨 Simulated Risk: {sim_risk}")
                    elif sim_risk == "Medium":
                        st.warning(f"⚠️ Simulated Risk: {sim_risk}")
                    else:
                        st.success(f"✅ Simulated Risk: {sim_risk}")

                    st.write(f"**Confidence Score:** {sim_confidence:.2f}%")
                    st.write(f"**Model Used:** {sim_model_choice}")

                    sim_recommendations = get_recommendation(sim_risk)
                    st.markdown("### Suggested Action")
                    for rec in sim_recommendations:
                        st.write(f"- {rec}")

        elif menu_choice == "📚 Courses":
            require_staff()
            st.subheader("📚 Courses")

            st.markdown("### Add New Course")
            course_code = st.text_input("Course Code")
            course_name = st.text_input("Course Name")

            if st.button("Add Course", key="add_course_btn"):
                if course_code.strip() and course_name.strip():
                    ok, msg = add_course(course_code.strip(), course_name.strip(), st.session_state.user)
                    if ok:
                        log_audit(
                            st.session_state.user,
                            "Course Added",
                            f"Course: {course_code.strip()} - {course_name.strip()}"
                        )
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Please fill in course code and course name.")

            st.markdown("### My Courses")
            courses_df = load_courses_by_lecturer(st.session_state.user)
            if courses_df.empty:
                st.info("You have not added any courses yet.")
            else:
                st.dataframe(courses_df, use_container_width=True)

            st.markdown("### Enroll Student in My Course")
            enroll_student_id = st.text_input("Student ID to Enroll")
            if not courses_df.empty:
                enroll_course_code = st.selectbox(
                    "Select Course to Enroll",
                    courses_df["course_code"].tolist(),
                    key="enroll_course_code"
                )

                if st.button("Enroll Student", key="enroll_student_btn"):
                    if enroll_student_id.strip():
                        enroll_student(enroll_student_id.strip(), enroll_course_code)
                        log_audit(
                            st.session_state.user,
                            "Student Enrolled",
                            f"Student: {enroll_student_id.strip()}, Course: {enroll_course_code}"
                        )
                        create_notification_if_new(
                            enroll_student_id.strip(),
                            "Course Enrollment",
                            f"You have been enrolled in {enroll_course_code}."
                        )
                        st.success("Student enrolled successfully.")
                    else:
                        st.warning("Please enter student ID.")

        elif menu_choice == "📝 Results Upload":
            require_staff()
            st.subheader("📝 Upload Student Results")

            courses_df = load_courses_by_lecturer(st.session_state.user)

            if courses_df.empty:
                st.warning("You have no courses assigned. Add a course first.")
            else:
                course_options = courses_df["course_code"].tolist()
                selected_course = st.selectbox(
                    "Select Your Course",
                    course_options,
                    key="results_course_select"
                )

                enrolled_students_df = load_students_by_course_for_lecturer(selected_course, st.session_state.user)

                if enrolled_students_df.empty:
                    st.info("No students are enrolled in this course yet.")
                else:
                    student_options = enrolled_students_df["student_id"].tolist()
                    selected_student_id = st.selectbox(
                        "Select Enrolled Student",
                        student_options,
                        key="results_student_select"
                    )

                    st.markdown("### Enter Scores")
                    test_score = st.number_input("Test Score", min_value=0.0, max_value=30.0, value=0.0, step=1.0, key="test_score_input")
                    assignment_score = st.number_input("Assignment Score", min_value=0.0, max_value=30.0, value=0.0, step=1.0, key="assignment_score_input")
                    exam_score = st.number_input("Exam Score", min_value=0.0, max_value=40.0, value=0.0, step=1.0, key="exam_score_input")

                    total_preview = test_score + assignment_score + exam_score
                    st.write(f"**Total Preview:** {total_preview:.1f} / 100")

                    if st.button("Upload Result", key="upload_result_btn"):
                        action, grade, total_score = save_result(
                            selected_student_id,
                            selected_course,
                            test_score,
                            assignment_score,
                            exam_score,
                            st.session_state.user
                        )
                        log_audit(
                            st.session_state.user,
                            "Result Saved",
                            f"Student: {selected_student_id}, Course: {selected_course}, Action: {action}, Grade: {grade}"
                        )
                        st.success(
                            f"Result {action} for {selected_student_id} in {selected_course}. Grade: {grade}, Total: {total_score:.1f}"
                        )

        elif menu_choice == "✏️ Results Manager":
            require_staff()
            st.subheader("✏️ Results Manager")

            results_df = load_results_for_lecturer(st.session_state.user)

            if results_df.empty:
                st.info("No results found for your courses.")
            else:
                st.dataframe(results_df, use_container_width=True)

                result_ids = results_df["id"].tolist()
                selected_result_id = st.selectbox("Select Result ID", result_ids, key="manage_result_id")

                selected_row = results_df[results_df["id"] == selected_result_id].iloc[0]

                st.markdown("### Edit Selected Result")
                edit_test = st.number_input("Edit Test Score", min_value=0.0, max_value=30.0, value=float(selected_row["test_score"]), step=1.0, key="edit_test")
                edit_assignment = st.number_input("Edit Assignment Score", min_value=0.0, max_value=30.0, value=float(selected_row["assignment_score"]), step=1.0, key="edit_assignment")
                edit_exam = st.number_input("Edit Exam Score", min_value=0.0, max_value=40.0, value=float(selected_row["exam_score"]), step=1.0, key="edit_exam")

                c1, c2 = st.columns(2)

                with c1:
                    if st.button("Update Result", key="update_result_btn"):
                        updated, grade, total_score = update_result(
                            selected_result_id,
                            edit_test,
                            edit_assignment,
                            edit_exam,
                            st.session_state.user
                        )
                        if updated:
                            log_audit(
                                st.session_state.user,
                                "Result Updated",
                                f"Result ID: {selected_result_id}, Student: {selected_row['student_id']}, Course: {selected_row['course_code']}, Grade: {grade}"
                            )
                            create_notification_if_new(
                                selected_row["student_id"],
                                "Result Update",
                                f"Your result for {selected_row['course_code']} has been updated. Grade: {grade}, Total: {total_score:.1f}"
                            )
                            st.success("Result updated successfully.")
                            st.rerun()
                        else:
                            st.warning("Result update failed.")

                with c2:
                    if st.button("Delete Result", key="delete_result_btn"):
                        deleted = delete_result(selected_result_id)
                        if deleted:
                            log_audit(
                                st.session_state.user,
                                "Result Deleted",
                                f"Result ID: {selected_result_id}, Student: {selected_row['student_id']}, Course: {selected_row['course_code']}"
                            )
                            st.success("Result deleted successfully.")
                            st.rerun()
                        else:
                            st.warning("Result deletion failed.")

        elif menu_choice == "📤 Reports":
            require_staff()
            st.subheader("📤 Reports")

        elif menu_choice == "🗓 Attendance":
            require_staff()
            st.subheader("🗓 Attendance Tracking")

            courses_df = load_courses_by_lecturer(st.session_state.user) if st.session_state.role == "lecturer" else load_courses()

            if courses_df.empty:
                st.info("No courses available.")
            else:
                selected_course = st.selectbox(
                    "Select Course",
                    courses_df["course_code"].tolist(),
                    key="attendance_course_select"
                )

                students_df = load_students_by_course(selected_course)
                if students_df.empty:
                    st.info("No enrolled students in this course.")
                else:
                    selected_student = st.selectbox(
                        "Select Student",
                        students_df["student_id"].tolist(),
                        key="attendance_student_select"
                    )

                    attendance_date = st.date_input("Attendance Date", value=date.today(), key="attendance_date")
                    attendance_status = st.selectbox("Status", ["Present", "Absent"], key="attendance_status")

                    if st.button("Save Attendance", key="save_attendance_btn"):
                        action = mark_attendance(
                            selected_student,
                            selected_course,
                            str(attendance_date),
                            attendance_status,
                            st.session_state.user
                        )
                        log_audit(
                            st.session_state.user,
                            "Attendance Saved",
                            f"Student: {selected_student}, Course: {selected_course}, Date: {attendance_date}, Status: {attendance_status}, Action: {action}"
                        )
                        st.success(f"Attendance {action} successfully.")

                    st.markdown("### Attendance History")
                    attendance_df = load_attendance_by_course(selected_course)
                    if attendance_df.empty:
                        st.info("No attendance records yet.")
                    else:
                        st.dataframe(attendance_df, use_container_width=True)

            st.markdown("### Export Student Case Report")
            student_profiles_df = load_all_student_profiles()

            if student_profiles_df.empty:
                st.info("No student profiles found for case report export.")
            else:
                student_ids = student_profiles_df["student_id"].tolist()
                selected_case_student = st.selectbox("Select Student for Case Report", student_ids, key="case_report_student")

                if st.button("Generate Student Case PDF", key="generate_student_case_pdf_btn"):
                    pdf_buffer = generate_student_case_profile_pdf(selected_case_student)
                    log_audit(
                        st.session_state.user,
                        "Student Case Report Exported",
                        f"Student: {selected_case_student}"
                    )
                    st.download_button(
                        label="Download Student Case PDF",
                        data=pdf_buffer,
                        file_name=f"student_case_report_{selected_case_student}.pdf",
                        mime="application/pdf",
                        key="download_case_pdf_btn"
                    )

            st.markdown("### Export Class Results CSV")
            lecturer_courses_df = load_courses_by_lecturer(st.session_state.user)

            if lecturer_courses_df.empty:
                st.info("You have no courses available for class report export.")
            else:
                selected_report_course = st.selectbox(
                    "Select Course for Class Results Export",
                    lecturer_courses_df["course_code"].tolist(),
                    key="report_course_select"
                )

                if st.button("Generate Class Results CSV", key="generate_class_csv_btn"):
                    csv_data = generate_class_results_csv(selected_report_course, st.session_state.user)
                    log_audit(
                        st.session_state.user,
                        "Class Results Exported",
                        f"Course: {selected_report_course}"
                    )
                    st.download_button(
                        label="Download Class Results CSV",
                        data=csv_data,
                        file_name=f"class_results_{selected_report_course}.csv",
                        mime="text/csv",
                        key="download_class_csv_btn"
                    )
        elif menu_choice == "👑 Admin Dashboard":
            require_admin()
            st.subheader("👑 Admin Dashboard")

            summary = get_system_summary()
            users_df = load_all_users()
            latest_df = get_latest_predictions_df()
            audit_df = load_audit_logs()
 
            st.markdown("""
            <div class="staff-banner">
                <h2 style='margin-bottom:6px;'>Administrator Control Center</h2>
                <p style='margin:0;'>System-wide monitoring, user oversight, and operational control.</p>
            </div>
            """, unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Users", summary["users"])
            c2.metric("Students", summary["students"])
            c3.metric("Lecturers", summary["lecturers"])
            c4.metric("Admins", summary["admins"])

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Predictions", summary["predictions"])
            c6.metric("Courses", summary["courses"])
            c7.metric("Results", summary["results"])
            c8.metric("Notifications", summary["notifications"])

            st.markdown("### 🧭 Admin Overview")

            a1, a2 = st.columns(2)

            with a1:
                 st.markdown("""
                 <div class="staff-panel">
                     <h4>👥 User Role Distribution</h4>
                 </div>
                 """, unsafe_allow_html=True)

                 role_counts = pd.DataFrame([
                     {"Role": "Students", "Count": summary["students"]},
                     {"Role": "Lecturers", "Count": summary["lecturers"]},
                     {"Role": "Advisors", "Count": summary["advisors"]},
                     {"Role": "Admins", "Count": summary["admins"]}
                 ])
                 st.dataframe(role_counts, use_container_width=True)

            with a2:
                st.markdown("""
                <div class="staff-panel">
                    <h4>🚨 Current High-Risk Snapshot</h4>
                </div>
                """, unsafe_allow_html=True)

                if latest_df.empty:
                    st.info("No latest prediction data available.")
                else:
                    high_df = latest_df[latest_df["risk_level"] == "High"]
                    if high_df.empty:
                        st.success("No current high-risk students.")
                    else:
                        st.dataframe(
                            high_df[["student_id", "risk_level", "confidence", "created_at"]],
                            use_container_width=True
                        )

            st.markdown("### ⚡ Quick Admin Actions")

            q1, q2, q3 = st.columns(3)

            with q1:
                if st.button("👥 Open User Management", use_container_width=True, key="admin_jump_users"):
                     st.session_state.nav_group = "Administration"
                     st.session_state.menu_choice = "👥 User Management"
                     st.rerun()

            with q2:
                if st.button("📨 Open Notification Center", use_container_width=True, key="admin_jump_notifications"):
                    st.session_state.nav_group = "Administration"
                    st.session_state.menu_choice = "📨 Notification Center"
                    st.rerun()

            with q3:
                if st.button("🧾 Open Audit Trail", use_container_width=True, key="admin_jump_audit"):
                    st.session_state.nav_group = "System Information"
                    st.session_state.menu_choice = "🧾 Audit Trail"
                    st.rerun()

            st.markdown("### 🕒 Recent System Activity")

            if audit_df.empty:
                st.info("No recent audit activity available.")
            else:
                st.dataframe(audit_df.head(10), use_container_width=True)
        
            st.markdown("### 📌 Admin-Only Insights")
            st.write("- Monitor total platform usage across all roles.")
            st.write("- Review current high-risk cases at institutional level.")
            st.write("- Jump directly to user, notification, and audit controls.")
            st.write("- Use the admin dashboard as a system control center, not an academic working page.")

        elif menu_choice == "🧾 Audit Trail":
            require_staff()
            st.subheader("🧾 Audit Trail")

            audit_df = load_audit_logs()
            if audit_df.empty:
                st.info("No audit logs yet.")
            else:
                st.dataframe(audit_df, use_container_width=True)

        elif menu_choice == "ℹ️ About SAPES":
            st.subheader("ℹ️ About SAPES")
            st.markdown("""
            ### What is SAPES?
            SAPES stands for **Student Academic Performance Early-Warning System**.
            It is an intelligent academic support system designed to identify students who may be at risk academically.

            ### Core Purpose
            The system helps lecturers and academic staff:
            - predict student risk levels early
            - monitor academic indicators
            - track student history
            - record interventions
            - support timely academic decision-making

            ### Data Used by the Model
            SAPES uses the following indicators:
            - Attendance
            - Quiz Average
            - Assignment Average
            - Midterm Score
            - Late Submissions
            - Previous GPA

            ### AI Models Used
            - Random Forest
            - Logistic Regression

            ### Why SAPES Matters
            SAPES goes beyond simple prediction by providing:
            - confidence scores
            - recommendations
            - trend tracking
            - intervention notes
            - analytics dashboards
            - course ownership
            - results management
            - reports
            - audit tracking
            - notification center
            - deployment-ready structure

            ### Ethical Use
            SAPES should support lecturers and advisors, not replace human judgment.
            Predictions should be used responsibly, fairly, and with academic care.
            """)
