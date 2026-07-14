"""
SG Fluid Technologies Pte Ltd — Company Website + Installer Verification Portal
--------------------------------------------------------------------------------
A single Flask application serving three audiences:

  1. PUBLIC visitors — browse the SG Fluid Technologies marketing site (home,
     inquiry form, thank-you page), and can verify a Lokring Installer ID
     (Cert #) at /verify to see whether it is Active / Expired / Pending.
     They cannot see the full installer list or add/edit/delete anything.

  2. ADMIN (Jack.D / SG Fluid Technologies staff) — logs in at /admin/login
     and, once authenticated, can view the full installer list and add,
     edit, or delete records via /admin.

Company positioning: SG Fluid Technologies Pte Ltd is the operating company
(major brand); Lokring Asia is the supplier/product line it distributes
(minor brand, credited throughout as "Distributor of Lokring Asia").

Key design points:
- SQLite database (`database.db`) auto-initializes on first run, seeded
  with 39 real installer records from the Lokring SG training tracker.
- Certification status ("Active" / "Expired" / "Pending/Not Yet Active")
  is NEVER stored in the database. It is calculated live, on every
  request, by comparing the installer's start_date / end_date against
  the current real-world date.
- All SQL queries use parameterized placeholders (`?`) to prevent SQL
  injection.
- Admin routes are protected by a `login_required` decorator that checks
  a signed Flask session cookie. Passwords are never stored or compared
  in plain text — they're hashed with werkzeug's PBKDF2 implementation.
- Search input is trimmed of whitespace and matched case-insensitively.

SECURITY NOTE FOR PRODUCTION USE:
Before deploying this anywhere public-facing, set these via real
environment variables rather than the defaults below:
    SECRET_KEY        -> any long random string
    ADMIN_USERNAME     -> your chosen admin username
    ADMIN_PASSWORD     -> your chosen admin password
The defaults are only meant for local testing in VS Code.
"""

import sqlite3
import os
from datetime import date, datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Session cookies need a secret key to be signed/tamper-proof. In production,
# set SECRET_KEY as a real environment variable instead of using this default.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-in-production")

DB_NAME = "database.db"

# ---------------------------------------------------------------------------
# Company updates / events feed — upload configuration
# ---------------------------------------------------------------------------
UPLOAD_FOLDER = os.path.join("static", "uploads", "posts")
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_IMAGES_PER_POST = 6
MAX_WORDS_PER_POST = 5000

# Safety net on total request size (covers up to 6 images comfortably).
# Without this, an unbounded upload could exhaust server memory/disk.
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB per request

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------------------------------------------------------------------
# Admin credentials
# ---------------------------------------------------------------------------
# Read from environment variables if set, otherwise fall back to a default
# so the app still runs out-of-the-box in VS Code. CHANGE THESE before
# putting the site anywhere public — see README.md.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(
    os.environ.get("ADMIN_PASSWORD", "changeme123")
)


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------
def init_db():
    """
    Creates the SQLite database and `installers` table if it does not
    already exist, then seeds it with the 39 real installer records from
    Jack.D's "Lokring Certified Training Program History Records (SG)"
    Excel tracker. installer_id = Lokring Certificate #; start_date = Date
    of Completion; end_date = Date of Expiry.

    This seed step only runs ONCE — if database.db already exists, existing
    data (including anything added later via the admin panel) is untouched.
    """
    db_exists = os.path.exists(DB_NAME)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS installers (
            installer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            company TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL
        )
    """)

    # Company updates / events feed (LinkedIn-style posts): one title + up to
    # 5000 words of body text + up to 6 images per post. Images are stored as
    # files on disk (static/uploads/posts/) with just their filenames recorded
    # here, ordered by `position` (0-5) so they display in the order the admin
    # arranged them. `is_featured` marks posts the admin has chosen to
    # highlight in the "Company Event" section on the homepage (max 3 at a
    # time -- enforced in the admin_post_feature route, not by the schema).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_featured INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Migration safety net: if posts already existed from before is_featured
    # was introduced, add the column so existing installs don't break.
    existing_columns = [row[1] for row in cursor.execute("PRAGMA table_info(posts)").fetchall()]
    if "is_featured" not in existing_columns:
        cursor.execute("ALTER TABLE posts ADD COLUMN is_featured INTEGER NOT NULL DEFAULT 0")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS post_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            position INTEGER NOT NULL,
            FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
        )
    """)

    if not db_exists:
        # NOTE: For Cert #189011-189017 (Shing Leck Engineering / Exxonmobil
        # Singapore), the source sheet listed an expiry date one day BEFORE
        # the completion date -- corrected to 2029-03-17 per Jack.D's
        # confirmation, matching the "3 years minus 1 day" pattern used by
        # every other batch.
        real_records = [
            ('187733', 'Francisco Segovia Jr.', 'Petracarbon Pte. Ltd.', '2025-11-26', '2028-11-25'),
            ('187734', 'Aidil Amirul B. Alias', 'Petracarbon Pte. Ltd.', '2025-11-26', '2028-11-25'),
            ('187735', 'Metta Paparao', 'Petracarbon Pte. Ltd.', '2025-11-26', '2028-11-25'),
            ('187736', 'Ashokkumar Prabaharan', 'Petracarbon Pte. Ltd.', '2025-11-26', '2028-11-25'),
            ('187674', 'ALVIN RUSLI', 'PT SAKA NUSA PERSADA', '2025-10-30', '2028-10-29'),
            ('187675', 'JULIUS ALDO RUSLI', 'PT SAKA NUSA PERSADA', '2025-10-30', '2028-10-29'),
            ('187676', 'ERICK', 'PT SAKA NUSA PERSADA', '2025-10-30', '2028-10-29'),
            ('187677', 'RADITYA YOGASWARA HERMAN', 'PT SAKA NUSA PERSADA', '2025-10-30', '2028-10-29'),
            ('187678', 'KHOIRUL FATA', 'PT SAKA NUSA PERSADA', '2025-10-30', '2028-10-29'),
            ('184886', 'CHONG CHEONG YI', 'ASIAN SEALAND OFFSHORE & MARINE PTE LTD', '2025-07-07', '2028-07-06'),
            ('184887', 'CHAN CHENG KEONG', 'ASIAN SEALAND OFFSHORE & MARINE PTE LTD', '2025-07-07', '2028-07-06'),
            ('184888', 'FAIZ FAZARI', 'ASIAN SEALAND OFFSHORE & MARINE PTE LTD', '2025-07-07', '2028-07-06'),
            ('184889', 'KARIN TEO', 'ASIAN SEALAND OFFSHORE & MARINE PTE LTD', '2025-07-07', '2028-07-06'),
            ('184936', 'Worarak Chaiwongworanont', 'Petracarbon Thailand', '2025-07-14', '2028-07-13'),
            ('184937', 'Tana Sri-on', 'Petracarbon Thailand', '2025-07-14', '2028-07-13'),
            ('184938', 'Pongnarin Boonjan', 'Petracarbon Thailand', '2025-07-14', '2028-07-13'),
            ('184939', 'Voradech Santiphanusophon', 'Petracarbon Thailand', '2025-07-14', '2028-07-13'),
            ('184940', 'Samrit Ngamlamai', 'Petracarbon Thailand', '2025-07-14', '2028-07-13'),
            ('184941', 'Ratthanin Phopan', 'Petracarbon Thailand', '2025-07-14', '2028-07-13'),
            ('187101', 'MIAH MD OSMAN', 'SIN EE KIANG ENGINEERING & CONSTRUCTION PTE LTD', '2025-10-02', '2028-10-01'),
            ('187102', 'ARIMUTHU PALANI', 'SIN EE KIANG ENGINEERING & CONSTRUCTION PTE LTD', '2025-10-02', '2028-10-01'),
            ('187801', 'Amirul Haqimi Bin Hamdan', 'STEEK HAWK ENGINEERING SDN BHD', '2026-01-16', '2029-01-15'),
            ('187802', 'Mohd Amirul Syafiq Bin Zamri', 'STEEK HAWK ENGINEERING SDN BHD', '2026-01-16', '2029-01-15'),
            ('187803', 'MOHD AFIQ DANISH BIN MOHD AZLAN', 'STEEK HAWK ENGINEERING SDN BHD', '2026-01-16', '2029-01-15'),
            ('187804', 'MUHAMMAD NAZMI HAKIM BIN ZAINAL', 'STEEK HAWK ENGINEERING SDN BHD', '2026-01-16', '2029-01-15'),
            ('187805', 'AHMAD IKHMAL BIN OMAR', 'STEEK HAWK ENGINEERING SDN BHD', '2026-01-16', '2029-01-15'),
            ('187806', 'MOHD TARMIZI BIN HARUN', 'STEEK HAWK ENGINEERING SDN BHD', '2026-01-16', '2029-01-15'),
            ('187807', 'ADRIAN MAGHIMMADOSS', 'STEEK HAWK ENGINEERING SDN BHD', '2026-01-16', '2029-01-15'),
            ('188353', 'MAT SAHHADAN B. MOH HUROB', 'BAXTECH RESOURCES SDN BHD', '2026-02-01', '2029-01-31'),
            ('188354', 'MOHD ZUNAIDI B. ZAKARIA', 'BAXTECH RESOURCES SDN BHD', '2026-02-01', '2029-01-31'),
            ('188355', 'KHAIROY NIZAM B. HARUN', 'BAXTECH RESOURCES SDN BHD', '2026-02-01', '2029-01-31'),
            ('188356', 'MOHD SAYUTI B. SAMAH', 'BAXTECH RESOURCES SDN BHD', '2026-02-01', '2029-01-31'),
            ('189011', 'Jisam Md Shahadat Hosssaim', 'Shing Leck Engineering Service Pte Ltd', '2026-03-18', '2029-03-17'),
            ('189012', 'Islam Khaairul', 'Shing Leck Engineering Service Pte Ltd', '2026-03-18', '2029-03-17'),
            ('189013', 'Vennelavenkata Satyanarayana', 'Shing Leck Engineering Service Pte Ltd', '2026-03-18', '2029-03-17'),
            ('189014', 'Nagireddy Baskarran', 'Shing Leck Engineering Service Pte Ltd', '2026-03-18', '2029-03-17'),
            ('189015', 'Mohamad Fairus Bin Ismail', 'Exxonmobil Singapore', '2026-03-18', '2029-03-17'),
            ('189016', 'Muhammad Nazrul Bin Zainal', 'Exxonmobil Singapore', '2026-03-18', '2029-03-17'),
            ('189017', 'Shahrin', 'Exxonmobil Singapore', '2026-03-18', '2029-03-17'),
        ]
        cursor.executemany("""
            INSERT INTO installers (installer_id, name, company, start_date, end_date)
            VALUES (?, ?, ?, ?, ?)
        """, real_records)
        conn.commit()

    conn.close()


def get_db_connection():
    """Opens a new SQLite connection with row access by column name."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Core Status Logic
# ---------------------------------------------------------------------------
def evaluate_status(start_date_str, end_date_str):
    """
    Dynamically compares today's date against the installer's certification
    window and returns a human-readable status string.

    Rules:
        start_date <= today <= end_date   -> "Active"
        today > end_date                  -> "Expired"
        today < start_date                -> "Pending/Not Yet Active"
    """
    today = date.today()
    start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_date_str, "%Y-%m-%d").date()

    if start <= today <= end:
        return "Active"
    elif today > end:
        return "Expired"
    else:  # today < start
        return "Pending/Not Yet Active"


def format_display_date(date_str):
    """Converts 'YYYY-MM-DD' into a friendly display format, e.g. '14 Jul 2026'."""
    parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    return parsed.strftime("%d %b %Y")


def is_valid_date(date_str):
    """Returns True if date_str is a valid 'YYYY-MM-DD' date, else False."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Company updates / events feed — helpers
# ---------------------------------------------------------------------------
def allowed_image_file(filename):
    """True if filename has one of the allowed image extensions."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def count_words(text):
    """Simple whitespace-based word count, used to enforce the 5000-word cap."""
    return len(text.split())


def format_post_timestamp(iso_str):
    """Converts a stored ISO timestamp into a friendly display format."""
    parsed = datetime.strptime(iso_str, "%Y-%m-%d %H:%M:%S")
    return parsed.strftime("%d %b %Y, %I:%M %p")


def get_post_with_images(post_id):
    """Fetches a single post and its ordered list of image filenames, or None."""
    conn = get_db_connection()
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if post is None:
        conn.close()
        return None
    images = conn.execute(
        "SELECT id, filename FROM post_images WHERE post_id = ? ORDER BY position",
        (post_id,)
    ).fetchall()
    conn.close()
    return {
        "id": post["id"],
        "title": post["title"],
        "content": post["content"],
        "created_at": post["created_at"],
        "updated_at": post["updated_at"],
        "created_display": format_post_timestamp(post["created_at"]),
        "updated_display": format_post_timestamp(post["updated_at"]),
        "is_featured": bool(post["is_featured"]),
        "images": [dict(row) for row in images],
    }


def get_all_posts_with_images():
    """Fetches every post (newest first), each with its ordered image list."""
    conn = get_db_connection()
    posts = conn.execute("SELECT * FROM posts ORDER BY created_at DESC, id DESC").fetchall()

    results = []
    for post in posts:
        images = conn.execute(
            "SELECT id, filename FROM post_images WHERE post_id = ? ORDER BY position",
            (post["id"],)
        ).fetchall()
        results.append({
            "id": post["id"],
            "title": post["title"],
            "content": post["content"],
            "created_at": post["created_at"],
            "updated_at": post["updated_at"],
            "created_display": format_post_timestamp(post["created_at"]),
            "updated_display": format_post_timestamp(post["updated_at"]),
            "is_featured": bool(post["is_featured"]),
            "images": [dict(row) for row in images],
        })
    conn.close()
    return results


def get_featured_posts(limit=3):
    """
    Fetches up to `limit` admin-featured posts (most recently featured/
    updated first) for display in the homepage "Company Event" section.
    """
    conn = get_db_connection()
    posts = conn.execute(
        "SELECT * FROM posts WHERE is_featured = 1 ORDER BY updated_at DESC, id DESC LIMIT ?",
        (limit,)
    ).fetchall()

    results = []
    for post in posts:
        images = conn.execute(
            "SELECT id, filename FROM post_images WHERE post_id = ? ORDER BY position",
            (post["id"],)
        ).fetchall()
        results.append({
            "id": post["id"],
            "title": post["title"],
            "content": post["content"],
            "created_display": format_post_timestamp(post["created_at"]),
            "images": [dict(row) for row in images],
        })
    conn.close()
    return results


def save_uploaded_images(post_id, files, start_position=0):
    """
    Saves a list of uploaded image files to disk and inserts corresponding
    rows into post_images, starting at start_position. Returns the number of
    images actually saved (files with disallowed extensions are skipped).
    """
    import uuid

    conn = get_db_connection()
    position = start_position
    saved_count = 0

    for file in files:
        if file and file.filename and allowed_image_file(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, unique_name))
            conn.execute(
                "INSERT INTO post_images (post_id, filename, position) VALUES (?, ?, ?)",
                (post_id, unique_name, position)
            )
            position += 1
            saved_count += 1

    conn.commit()
    conn.close()
    return saved_count


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(view_func):
    """
    Decorator for admin-only routes. Redirects to the login page (with a
    'next' param so the user lands back where they intended) if there is
    no authenticated admin session.
    """
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# PUBLIC Routes — Marketing Site
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    """SG Fluid Technologies / Lokring Asia marketing homepage."""
    featured_posts = get_featured_posts(limit=3)
    return render_template("home.html", featured_posts=featured_posts)


@app.route("/thanks", methods=["GET"])
def thanks():
    """Shown after a visitor submits the engineering inquiry form on the homepage."""
    return render_template("thanks.html")


# ---------------------------------------------------------------------------
# PUBLIC Routes — Installer Verification
# ---------------------------------------------------------------------------
@app.route("/verify", methods=["GET", "POST"])
def verify():
    """
    Public installer verification page.
    GET  -> renders the initial page with just the search bar.
    POST -> handles the search submission:
              1. Trims whitespace from the submitted Installer ID.
              2. Runs a case-insensitive, parameterized lookup.
              3. If found, computes live status + formats dates for display.
              4. If not found, flags a "no match" state for the template.
    Visitors can ONLY search here -- there is no way to view the full list,
    add, edit, or delete records without logging in via /admin/login.
    """
    result = None
    searched_id = None
    no_match = False

    if request.method == "POST":
        raw_input = request.form.get("installer_id", "")
        searched_id = raw_input.strip()

        if searched_id:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Case-insensitive, parameterized query (SQL-injection safe).
            cursor.execute("""
                SELECT installer_id, name, company, start_date, end_date
                FROM installers
                WHERE UPPER(installer_id) = UPPER(?)
            """, (searched_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                status = evaluate_status(row["start_date"], row["end_date"])
                result = {
                    "installer_id": row["installer_id"],
                    "name": row["name"],
                    "company": row["company"],
                    "start_date": format_display_date(row["start_date"]),
                    "end_date": format_display_date(row["end_date"]),
                    "status": status,
                }
            else:
                no_match = True

    return render_template(
        "verify.html",
        result=result,
        no_match=no_match,
        searched_id=searched_id,
    )


# ---------------------------------------------------------------------------
# ADMIN Routes
# ---------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login form. On success, marks the session as authenticated."""
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Constant-shape check: verify username match AND password hash match.
        # check_password_hash is used (never plain '=='), so the real
        # password is never stored anywhere in comparable plain text.
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["is_admin"] = True
            session["admin_username"] = username
            next_url = request.args.get("next")
            return redirect(next_url or url_for("admin_dashboard"))
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    """Clears the admin session."""
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin", methods=["GET"])
@login_required
def admin_dashboard():
    """
    Admin dashboard: lists every installer record with its live-computed
    status, plus a form to add a new record. Edit/delete happen via the
    routes below.
    """
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT installer_id, name, company, start_date, end_date
        FROM installers
        ORDER BY installer_id
    """).fetchall()
    conn.close()

    installers = []
    for row in rows:
        installers.append({
            "installer_id": row["installer_id"],
            "name": row["name"],
            "company": row["company"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "status": evaluate_status(row["start_date"], row["end_date"]),
        })

    return render_template("admin_dashboard.html", installers=installers)


@app.route("/admin/add", methods=["POST"])
@login_required
def admin_add():
    """
    Adds a new installer record. Validates:
      - all fields present and non-empty
      - dates are valid YYYY-MM-DD and start_date <= end_date
      - installer_id (Cert #) isn't already in use (PRIMARY KEY collision)
    """
    installer_id = request.form.get("installer_id", "").strip()
    name = request.form.get("name", "").strip()
    company = request.form.get("company", "").strip()
    start_date_str = request.form.get("start_date", "").strip()
    end_date_str = request.form.get("end_date", "").strip()

    if not all([installer_id, name, company, start_date_str, end_date_str]):
        flash("All fields are required.", "error")
        return redirect(url_for("admin_dashboard"))

    if not is_valid_date(start_date_str) or not is_valid_date(end_date_str):
        flash("Dates must be valid (YYYY-MM-DD).", "error")
        return redirect(url_for("admin_dashboard"))

    if start_date_str > end_date_str:
        flash("Start date must be on or before the end date.", "error")
        return redirect(url_for("admin_dashboard"))

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO installers (installer_id, name, company, start_date, end_date)
            VALUES (?, ?, ?, ?, ?)
        """, (installer_id, name, company, start_date_str, end_date_str))
        conn.commit()
        flash(f"Installer {installer_id} added successfully.", "success")
    except sqlite3.IntegrityError:
        # installer_id already exists (PRIMARY KEY collision)
        flash(f"Installer ID '{installer_id}' already exists. Use Edit instead.", "error")
    finally:
        conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/edit/<installer_id>", methods=["POST"])
@login_required
def admin_edit(installer_id):
    """Updates an existing installer record's details."""
    name = request.form.get("name", "").strip()
    company = request.form.get("company", "").strip()
    start_date_str = request.form.get("start_date", "").strip()
    end_date_str = request.form.get("end_date", "").strip()

    if not all([name, company, start_date_str, end_date_str]):
        flash("All fields are required.", "error")
        return redirect(url_for("admin_dashboard"))

    if not is_valid_date(start_date_str) or not is_valid_date(end_date_str):
        flash("Dates must be valid (YYYY-MM-DD).", "error")
        return redirect(url_for("admin_dashboard"))

    if start_date_str > end_date_str:
        flash("Start date must be on or before the end date.", "error")
        return redirect(url_for("admin_dashboard"))

    conn = get_db_connection()
    conn.execute("""
        UPDATE installers
        SET name = ?, company = ?, start_date = ?, end_date = ?
        WHERE installer_id = ?
    """, (name, company, start_date_str, end_date_str, installer_id))
    conn.commit()
    conn.close()

    flash(f"Installer {installer_id} updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete/<installer_id>", methods=["POST"])
@login_required
def admin_delete(installer_id):
    """Deletes an installer record."""
    conn = get_db_connection()
    conn.execute("DELETE FROM installers WHERE installer_id = ?", (installer_id,))
    conn.commit()
    conn.close()

    flash(f"Installer {installer_id} deleted.", "success")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# PUBLIC Route — Company Updates / Events Feed
# ---------------------------------------------------------------------------
@app.route("/updates", methods=["GET"])
def updates():
    """
    Public LinkedIn-style feed of company event/update posts, newest first.
    Anyone can view. Edit/Delete controls only render (in the template) when
    the visitor is logged in as admin -- this route itself doesn't gate
    viewing, only the actual add/edit/delete routes below do.
    """
    posts = get_all_posts_with_images()
    return render_template("updates.html", posts=posts)


# ---------------------------------------------------------------------------
# ADMIN Routes — Company Updates / Events Feed
# ---------------------------------------------------------------------------
@app.route("/admin/posts/new", methods=["GET", "POST"])
@login_required
def admin_post_new():
    """
    Create a new company update post. Validates:
      - title and content are non-empty
      - content is at most 5000 words
      - at most 6 images are attached (extra files beyond 6 are ignored)
    """
    if request.method == "GET":
        return render_template("post_form.html", post=None, mode="new")

    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    uploaded_files = request.files.getlist("images")

    if not title or not content:
        flash("Title and content are both required.", "error")
        return render_template("post_form.html", post=None, mode="new")

    if count_words(content) > MAX_WORDS_PER_POST:
        flash(f"Content is too long ({count_words(content)} words). Maximum is {MAX_WORDS_PER_POST} words.", "error")
        return render_template("post_form.html", post=None, mode="new")

    # Only count files that actually have a name (empty file inputs still
    # show up in getlist as a single empty-filename entry).
    real_files = [f for f in uploaded_files if f and f.filename]
    if len(real_files) > MAX_IMAGES_PER_POST:
        flash(f"You attached {len(real_files)} images. Maximum is {MAX_IMAGES_PER_POST} per post.", "error")
        return render_template("post_form.html", post=None, mode="new")

    invalid_files = [f.filename for f in real_files if not allowed_image_file(f.filename)]
    if invalid_files:
        flash(f"Unsupported image type: {', '.join(invalid_files)}. Allowed: jpg, jpeg, png, gif, webp.", "error")
        return render_template("post_form.html", post=None, mode="new")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO posts (title, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (title, content, now_str, now_str)
    )
    new_post_id = cursor.lastrowid
    conn.commit()
    conn.close()

    if real_files:
        save_uploaded_images(new_post_id, real_files)

    flash("Post published successfully.", "success")
    return redirect(url_for("updates"))


@app.route("/admin/posts/edit/<int:post_id>", methods=["GET", "POST"])
@login_required
def admin_post_edit(post_id):
    """
    Edit an existing post's title/content, remove selected existing images,
    and/or add new images (total existing-kept + new must stay <= 6).
    """
    post = get_post_with_images(post_id)
    if post is None:
        flash("Post not found.", "error")
        return redirect(url_for("updates"))

    if request.method == "GET":
        return render_template("post_form.html", post=post, mode="edit")

    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    remove_ids = set(request.form.getlist("remove_images"))  # image ids checked for removal
    uploaded_files = [f for f in request.files.getlist("images") if f and f.filename]

    if not title or not content:
        flash("Title and content are both required.", "error")
        return render_template("post_form.html", post=post, mode="edit")

    if count_words(content) > MAX_WORDS_PER_POST:
        flash(f"Content is too long ({count_words(content)} words). Maximum is {MAX_WORDS_PER_POST} words.", "error")
        return render_template("post_form.html", post=post, mode="edit")

    kept_count = len([img for img in post["images"] if str(img["id"]) not in remove_ids])
    if kept_count + len(uploaded_files) > MAX_IMAGES_PER_POST:
        flash(f"Too many images: {kept_count} kept + {len(uploaded_files)} new exceeds the {MAX_IMAGES_PER_POST} limit.", "error")
        return render_template("post_form.html", post=post, mode="edit")

    invalid_files = [f.filename for f in uploaded_files if not allowed_image_file(f.filename)]
    if invalid_files:
        flash(f"Unsupported image type: {', '.join(invalid_files)}. Allowed: jpg, jpeg, png, gif, webp.", "error")
        return render_template("post_form.html", post=post, mode="edit")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    conn.execute(
        "UPDATE posts SET title = ?, content = ?, updated_at = ? WHERE id = ?",
        (title, content, now_str, post_id)
    )

    # Remove any images the admin checked for deletion (both the DB row and
    # the actual file on disk).
    for img in post["images"]:
        if str(img["id"]) in remove_ids:
            conn.execute("DELETE FROM post_images WHERE id = ?", (img["id"],))
            file_path = os.path.join(UPLOAD_FOLDER, img["filename"])
            if os.path.exists(file_path):
                os.remove(file_path)

    conn.commit()
    conn.close()

    if uploaded_files:
        # New images continue the position sequence after whatever was kept.
        save_uploaded_images(post_id, uploaded_files, start_position=kept_count)

    flash("Post updated successfully.", "success")
    return redirect(url_for("updates"))


@app.route("/admin/posts/delete/<int:post_id>", methods=["POST"])
@login_required
def admin_post_delete(post_id):
    """Deletes a post, its image records, and the image files on disk."""
    post = get_post_with_images(post_id)
    if post is None:
        flash("Post not found.", "error")
        return redirect(url_for("updates"))

    for img in post["images"]:
        file_path = os.path.join(UPLOAD_FOLDER, img["filename"])
        if os.path.exists(file_path):
            os.remove(file_path)

    conn = get_db_connection()
    conn.execute("DELETE FROM post_images WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()

    flash("Post deleted.", "success")
    return redirect(url_for("updates"))


@app.route("/admin/posts/feature/<int:post_id>", methods=["POST"])
@login_required
def admin_post_feature(post_id):
    """
    Toggles whether a post is featured in the homepage "Company Event"
    section. At most 3 posts may be featured at once -- trying to feature
    a 4th is rejected with a clear error asking the admin to unfeature one
    first, rather than silently bumping an existing one.
    """
    conn = get_db_connection()
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()

    if post is None:
        conn.close()
        flash("Post not found.", "error")
        return redirect(url_for("updates"))

    if post["is_featured"]:
        # Un-feature is always allowed.
        conn.execute("UPDATE posts SET is_featured = 0 WHERE id = ?", (post_id,))
        conn.commit()
        conn.close()
        flash(f'"{post["title"]}" removed from Company Event.', "success")
    else:
        featured_count = conn.execute(
            "SELECT COUNT(*) as c FROM posts WHERE is_featured = 1"
        ).fetchone()["c"]

        if featured_count >= 3:
            conn.close()
            flash("Only 3 posts can be featured at once. Unfeature one first.", "error")
        else:
            conn.execute("UPDATE posts SET is_featured = 1 WHERE id = ?", (post_id,))
            conn.commit()
            conn.close()
            flash(f'"{post["title"]}" added to Company Event.', "success")

    return redirect(url_for("updates"))


# ---------------------------------------------------------------------------
# Database initialization -- runs at import time
# ---------------------------------------------------------------------------
# This must NOT be inside the `if __name__ == "__main__":` block below, because
# production WSGI servers (gunicorn, etc., as used on Render/Railway/etc.)
# import this file as a module and never execute that block directly -- they
# just look for the `app` object. Calling init_db() here ensures the database
# is created/seeded correctly whether you run this with `python app.py`,
# VS Code's debugger, or a production server.
init_db()


if __name__ == "__main__":
    # VS Code friendly startup:
    # - Reads FLASK_DEBUG / PORT from the environment (set via .vscode/launch.json
    #   when running with the debugger, or a .env file / terminal export otherwise).
    # - Falls back to sensible local defaults if nothing is set, so `python app.py`
    #   from the integrated terminal just works with no extra configuration.
    # - host="0.0.0.0" so it also works correctly if you ever run this directly
    #   inside a container/cloud environment instead of via gunicorn.
    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    port = int(os.environ.get("PORT", 5000))

    app.run(host="0.0.0.0", port=port, debug=debug_mode)
