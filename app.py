# -*- coding: utf-8 -*-
"""
بک‌اند کتاب‌به‌کتاب — Flask + MySQL (برای تست محلی با XAMPP)

راه‌اندازی:
  1) XAMPP رو باز کن و فقط سرویس MySQL رو Start کن (به Apache نیازی نیست).
  2) اسکیمای دیتابیس رو بساز:  mysql -u root -p < schema.sql
     (اگه روی MySQL خودت پسورد نذاشتی، فقط بزن: mysql -u root < schema.sql)
  3) وابستگی‌ها رو نصب کن:     pip install -r requirements.txt
  4) اجرا کن:                  python app.py
  5) سایت روی http://127.0.0.1:5000 بالا میاد (همون‌جا هم API هست هم صفحات HTML)

اگه یوزر/پسورد MySQL روی سیستمت با مقادیر پایین فرق داره، DB_CONFIG رو ویرایش کن.
"""

import os
import uuid
import hashlib
import secrets
import smtplib
import time
from collections import defaultdict, deque
from threading import Lock
from datetime import datetime, timedelta
from email.message import EmailMessage
from hmac import compare_digest
from html import escape
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from flask import Flask, request, jsonify, session, send_from_directory, render_template
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import pooling
from mysql.connector import Error as MySQLError
try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # وابستگی در requirements نصب می‌شود؛ محیط سبک همچنان قابل import است.
    Image = None
    UnidentifiedImageError = Exception

# ---------- تنظیمات ----------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "ketabbeketab"),
    "autocommit": False,
}
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_TLS = os.getenv("SMTP_TLS", "1") == "1"
EMAIL_VERIFICATION_REQUIRED = os.getenv("EMAIL_VERIFICATION_REQUIRED", "1") == "1"
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
MAX_UPLOADS_PER_HOUR = int(os.getenv("MAX_UPLOADS_PER_HOUR", "20"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
COVERS_DIR = os.path.join(BASE_DIR, "covers")
BOOKS_DIR = os.path.join(BASE_DIR, "books")
GENERATED_BOOKS_DIR = os.path.join(BASE_DIR, "templates", "books")
TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, "_template.html")
os.makedirs(COVERS_DIR, exist_ok=True)
os.makedirs(BOOKS_DIR, exist_ok=True)
os.makedirs(GENERATED_BOOKS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
SHARE_TYPES = {"free", "deposit", "sale"}
VERIFICATION_MINUTES = 15
RATE_LIMIT_STORE = defaultdict(deque)
RATE_LIMIT_LOCK = Lock()

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static", template_folder=TEMPLATES_DIR)
configured_secret = os.getenv("SECRET_KEY")
if not configured_secret:
    configured_secret = secrets.token_hex(32)
    app.logger.warning("SECRET_KEY is not configured; sessions will reset after restart")
app.config.update(
    SECRET_KEY=configured_secret,
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
)
app.secret_key = app.config["SECRET_KEY"]


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response

try:
    DB_POOL = pooling.MySQLConnectionPool(pool_name="ketab_pool", pool_size=5, **DB_CONFIG)
except MySQLError:
    DB_POOL = None


@app.errorhandler(413)
def request_too_large(_error):
    return json_error("حجم فایل بیشتر از ۵ مگابایت است.", 413)


@app.errorhandler(MySQLError)
def database_error(_error):
    app.logger.exception("Database operation failed")
    return json_error("ارتباط با پایگاه‌داده برقرار نشد. دوباره تلاش کنید.", 503)


@app.route("/api/health")
def health():
    try:
        with db_cursor() as (_db, cur):
            cur.execute("SELECT 1")
        return jsonify(status="ok", database=True)
    except MySQLError:
        return jsonify(status="degraded", database=False), 503


# ---------- کمکی‌ها ----------
def get_db():
    """یک اتصال تازه یا اتصال استخر را برمی‌گرداند؛ خطا در زمان درخواست گزارش می‌شود."""
    return DB_POOL.get_connection() if DB_POOL else mysql.connector.connect(**DB_CONFIG)


@contextmanager
def db_cursor(dictionary=False):
    db = get_db()
    cur = db.cursor(dictionary=dictionary)
    try:
        yield db, cur
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()
        db.close()


def ensure_runtime_schema():
    """مهاجرت کوچک و بی‌خطر برای نصب‌های قدیمی که جدول تأیید ایمیل را ندارند."""
    try:
        with db_cursor() as (db, cur):
            cur.execute(
                """CREATE TABLE IF NOT EXISTS email_verifications (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    code_hash CHAR(64) NOT NULL,
                    expires_at DATETIME NOT NULL,
                    verified_at DATETIME NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_verifications_user (user_id, created_at),
                    INDEX idx_verifications_expiry (expires_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
            )
            db.commit()
    except MySQLError:
        app.logger.warning("Runtime schema migration skipped; run schema.sql before enabling email verification")


def json_error(message, status=400):
    return jsonify(error=message), status


def rate_limited(bucket, limit, window_seconds=300):
    """محدودکننده‌ی سبک برای جلوگیری از سوءاستفاده از endpointهای حساس."""
    now = time.monotonic()
    with RATE_LIMIT_LOCK:
        events = RATE_LIMIT_STORE[bucket]
        while events and now - events[0] > window_seconds:
            events.popleft()
        if len(events) >= limit:
            return True
        events.append(now)
    return False


def request_bucket(prefix, value=""):
    return f"{prefix}:{request.remote_addr or 'unknown'}:{value}"


ensure_runtime_schema()


def parse_amount(value, label):
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
        if number < 0 or number != number.to_integral_value():
            raise InvalidOperation
        return int(number)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label} باید یک عدد صحیح مثبت باشد.")


def hash_verification_code(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def send_verification_email(email, name, code):
    """ارسال کد با SMTP؛ در صورت تنظیم‌نشدن SMTP، False برمی‌گرداند."""
    if not SMTP_HOST or not SMTP_FROM:
        app.logger.warning("SMTP is not configured; verification email was not sent")
        return False
    message = EmailMessage()
    message["Subject"] = "کد تأیید ثبت‌نام کتاب‌به‌کتاب"
    message["From"] = SMTP_FROM
    message["To"] = email
    message.set_content(
        f"سلام {name}\n\nکد تأیید شما: {code}\nاین کد تا {VERIFICATION_MINUTES} دقیقه معتبر است.\n"
        f"\nصفحه‌ی ورود: {APP_BASE_URL}/login.html\n\nکتاب‌به‌کتاب"
    )
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_TLS:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        app.logger.exception("Verification email could not be sent")
        return False


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def valid_image_upload(file):
    if Image is None:
        file.stream.seek(0)
        header = file.stream.read(12)
        file.stream.seek(0)
        return (
            header.startswith(b"\x89PNG\r\n\x1a\n")
            or header.startswith(b"\xff\xd8\xff")
            or header.startswith((b"GIF87a", b"GIF89a"))
            or (header[:4] == b"RIFF" and header[8:12] == b"WEBP")
        )
    try:
        file.stream.seek(0)
        with Image.open(file.stream) as image:
            if image.format.lower() not in ALLOWED_EXTENSIONS:
                return False
            image.verify()
        file.stream.seek(0)
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        file.stream.seek(0)
        return False


def current_user_id():
    return session.get("user_id")


def book_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "author": row["author"],
        "genre": row["genre"],
        "condition": row["book_condition"],
        "shareType": row["share_type"],
        "duration": row["duration"],
        "depositAmount": row["deposit_amount"],
        "salePrice": row["sale_price"],
        "address": row["address"],
        "description": row["description"],
        "cover": f"/covers/{row['cover']}" if row.get("cover") else None,
        "ownerId": row["user_id"],
        "ownerName": row.get("owner_name"),
        "isMine": row["user_id"] == current_user_id(),
        "detailUrl": f"/books/book_{row['id']}.html",
    }


SHARE_TYPE_BADGE_LABELS = {"free": "امانت رایگان", "deposit": "امانت با ودیعه", "sale": "فروش"}


def build_request_rows_html(book):
    rows = []
    if book["share_type"] in ("free", "deposit") and book.get("duration"):
        rows.append(f'<div class="request-row"><span>مهلت امانت</span><span>{book["duration"]} روز</span></div>')
    if book["share_type"] == "deposit" and book.get("deposit_amount"):
        rows.append(f'<div class="request-row"><span>مبلغ ودیعه</span><span>{book["deposit_amount"]:,} تومان</span></div>')
    if book["share_type"] == "sale" and book.get("sale_price"):
        rows.append(f'<div class="request-row"><span>قیمت</span><span>{book["sale_price"]:,} تومان</span></div>')
    return "\n".join(rows)


def generate_book_page(book, owner_name):
    """از روی قالب books/_template.html، صفحه‌ی اختصاصیِ کتاب را می‌سازد."""
    if not os.path.exists(TEMPLATE_PATH):
        return  # قالب موجود نیست؛ صفحه ساخته نمی‌شود ولی بقیه‌ی سیستم کار می‌کند

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    cover_src = f"/covers/{book['cover']}" if book.get("cover") else "/static/images/logo.png"
    request_btn_label = "خرید می‌کنم" if book["share_type"] == "sale" else "امانت می‌گیرم"

    replacements = {
        "__TITLE__": escape(str(book["title"])),
        "__AUTHOR__": escape(str(book["author"])),
        "__GENRE__": escape(str(book["genre"])),
        "__CONDITION__": escape(str(book["book_condition"])),
        "__ADDRESS__": escape(str(book["address"])),
        "__DESCRIPTION__": escape(str(book.get("description") or "")).replace("\n", "<br>") ,
        "__OWNER_NAME__": escape(str(owner_name)),
        "__OWNER_ID__": str(book["user_id"]),
        "__BOOK_ID__": str(book["id"]),
        "__COVER_SRC__": cover_src,
        "__BADGE_CLASS__": book["share_type"],
        "__BADGE_LABEL__": SHARE_TYPE_BADGE_LABELS.get(book["share_type"], book["share_type"]),
        "__REQUEST_ROWS__": build_request_rows_html(book),
        "__REQUEST_BTN_LABEL__": request_btn_label,
    }

    for token, value in replacements.items():
        html = html.replace(token, str(value))

    out_path = os.path.join(GENERATED_BOOKS_DIR, f"book_{book['id']}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return f"/books/book_{book['id']}.html"


def delete_book_page(book_id):
    path = os.path.join(GENERATED_BOOKS_DIR, f"book_{book_id}.html")
    try:
        os.remove(path)
    except OSError:
        pass


# ---------- سرو کردن فایل‌های استاتیک سایت ----------
@app.route("/")
def serve_index():
    return render_template("index.html")


@app.route("/covers/<path:filename>")
def serve_cover(filename):
    return send_from_directory(COVERS_DIR, filename)


@app.route("/<path:filename>")
def serve_static_file(filename):
    template_path = os.path.join(TEMPLATES_DIR, filename)
    if os.path.isfile(template_path) and filename.lower().endswith(".html"):
        return render_template(filename.replace("\\", "/"))
    return send_from_directory(BASE_DIR, filename)


# ---------- احراز هویت ----------
@app.route("/api/register", methods=["POST"])
def register():
    if rate_limited(request_bucket("register"), 5):
        return json_error("تعداد تلاش‌ها زیاد است؛ چند دقیقه بعد دوباره امتحان کن.", 429)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""

    if len(name) < 2 or len(name) > 255 or "@" not in email or len(email) > 255 or len(password) < 8:
        return json_error("نام، ایمیل یا رمز عبور معتبر نیست.")

    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cur.fetchone():
                return json_error("این ایمیل قبلاً ثبت‌نام کرده است.", 409)

            password_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO users (name, email, phone, password_hash) VALUES (%s, %s, %s, %s)",
                (name, email, phone, password_hash),
            )
            user_id = cur.lastrowid
            code = f"{secrets.randbelow(1000000):06d}"
            cur.execute(
                "INSERT INTO email_verifications (user_id, code_hash, expires_at) VALUES (%s, %s, %s)",
                (user_id, hash_verification_code(code), datetime.utcnow() + timedelta(minutes=VERIFICATION_MINUTES)),
            )
            db.commit()
    except MySQLError as e:
        app.logger.exception("Registration failed")
        return json_error("ثبت‌نام انجام نشد. دوباره تلاش کنید.", 503)

    email_sent = send_verification_email(email, name, code)
    return jsonify(
        success=True,
        id=user_id,
        name=name,
        verificationRequired=EMAIL_VERIFICATION_REQUIRED,
        emailSent=email_sent,
    )


@app.route("/api/login", methods=["POST"])
def login():
    if rate_limited(request_bucket("login"), 10):
        return json_error("تعداد تلاش‌های ورود زیاد است؛ چند دقیقه بعد دوباره امتحان کن.", 429)
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute(
                """SELECT users.*,
                   EXISTS(SELECT 1 FROM email_verifications ev
                          WHERE ev.user_id=users.id AND ev.verified_at IS NOT NULL) AS email_verified
                   FROM users WHERE email=%s""",
                (email,),
            )
            user = cur.fetchone()
    except MySQLError as e:
        app.logger.exception("Login failed")
        return json_error("ورود انجام نشد. دوباره تلاش کنید.", 503)

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="ایمیل یا رمز عبور اشتباه است."), 401
    if EMAIL_VERIFICATION_REQUIRED and not user.get("email_verified"):
        return json_error("ابتدا کد تأیید ارسال‌شده به ایمیل را وارد کن.", 403)

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["is_admin"] = bool(user.get("is_admin"))
    return jsonify(success=True, id=user["id"], name=user["name"])


@app.route("/api/verify-email", methods=["POST"])
def verify_email():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()
    if rate_limited(request_bucket("verify", email), 8):
        return json_error("تعداد تلاش برای کد تأیید زیاد است؛ بعداً دوباره امتحان کن.", 429)
    if "@" not in email or len(code) != 6 or not code.isdigit():
        return json_error("ایمیل یا کد تأیید معتبر نیست.")

    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute(
                """SELECT ev.id, ev.code_hash, u.id AS user_id, u.name
                   FROM email_verifications ev JOIN users u ON u.id=ev.user_id
                   WHERE u.email=%s AND ev.verified_at IS NULL
                     AND ev.expires_at > UTC_TIMESTAMP()
                   ORDER BY ev.created_at DESC LIMIT 1""",
                (email,),
            )
            record = cur.fetchone()
            if not record or not compare_digest(record["code_hash"], hash_verification_code(code)):
                return json_error("کد تأیید اشتباه یا منقضی شده است.", 400)
            cur.execute("UPDATE email_verifications SET verified_at=UTC_TIMESTAMP() WHERE id=%s", (record["id"],))
            db.commit()
    except MySQLError:
        app.logger.exception("Email verification failed")
        return json_error("تأیید ایمیل انجام نشد.", 503)

    return jsonify(success=True, id=record["user_id"], name=record["name"])


@app.route("/api/resend-verification", methods=["POST"])
def resend_verification():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if rate_limited(request_bucket("resend", email), 3, 900):
        return json_error("تعداد ارسال مجدد زیاد است؛ کمی بعد دوباره امتحان کن.", 429)
    if "@" not in email:
        return json_error("ایمیل معتبر نیست.")
    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute("SELECT id, name FROM users WHERE email=%s", (email,))
            user = cur.fetchone()
            if not user:
                return jsonify(success=True, emailSent=False)
            code = f"{secrets.randbelow(1000000):06d}"
            cur.execute(
                "INSERT INTO email_verifications (user_id, code_hash, expires_at) VALUES (%s, %s, %s)",
                (user["id"], hash_verification_code(code), datetime.utcnow() + timedelta(minutes=VERIFICATION_MINUTES)),
            )
            db.commit()
    except MySQLError:
        app.logger.exception("Verification code resend failed")
        return json_error("ارسال دوباره‌ی کد انجام نشد.", 503)
    return jsonify(success=True, emailSent=send_verification_email(email, user["name"], code))


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(success=True)


@app.route("/api/me")
def me():
    if not current_user_id():
        return jsonify(loggedIn=False)
    return jsonify(loggedIn=True, id=session["user_id"], name=session["user_name"])


# ---------- کتاب‌ها ----------
@app.route("/api/books", methods=["GET"])
def list_books():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 24, type=int), 1), 100)
    search = (request.args.get("q") or "").strip()
    offset = (page - 1) * per_page
    try:
        with db_cursor(dictionary=True) as (_db, cur):
            query = """SELECT books.*, users.name AS owner_name FROM books
                       JOIN users ON books.user_id = users.id"""
            params = []
            if search:
                query += " WHERE books.title LIKE %s OR books.author LIKE %s OR books.genre LIKE %s"
                term = f"%{search}%"
                params.extend([term, term, term])
            query += " ORDER BY books.created_at DESC LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            cur.execute(query, params)
            rows = cur.fetchall()
    except MySQLError as e:
        app.logger.exception("Book listing failed")
        return json_error("دریافت کتاب‌ها انجام نشد.", 503)

    # قالب قدیمی سایت آرایه دریافت می‌کند؛ اطلاعات صفحه‌بندی از طریق هدرها نیز در دسترس است.
    response = jsonify([book_to_dict(r) for r in rows])
    response.headers["X-Page"] = str(page)
    response.headers["X-Per-Page"] = str(per_page)
    return response


@app.route("/api/my-books", methods=["GET"])
def my_books():
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401

    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute(
                """SELECT books.*, users.name AS owner_name
                   FROM books JOIN users ON books.user_id = users.id
                   WHERE books.user_id=%s ORDER BY books.created_at DESC""",
                (current_user_id(),),
            )
            rows = cur.fetchall()
    except MySQLError as e:
        app.logger.exception("My books listing failed")
        return json_error("دریافت کتاب‌های شما انجام نشد.", 503)

    return jsonify([book_to_dict(r) for r in rows])


@app.route("/api/books", methods=["POST"])
def add_book():
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401
    if rate_limited(request_bucket("upload", str(current_user_id())), MAX_UPLOADS_PER_HOUR, 3600):
        return json_error("تعداد آپلودهای امروز زیاد است؛ بعداً دوباره امتحان کن.", 429)

    title = (request.form.get("title") or "").strip()
    author = (request.form.get("author") or "").strip()
    genre = (request.form.get("genre") or "").strip()
    condition = (request.form.get("condition") or "").strip()
    share_type = (request.form.get("shareType") or "free").strip()
    address = (request.form.get("address") or "").strip()
    description = (request.form.get("description") or "").strip()

    try:
        duration = parse_amount(request.form.get("duration"), "مدت امانت")
        deposit_amount = parse_amount(request.form.get("depositAmount"), "ودیعه")
        sale_price = parse_amount(request.form.get("salePrice"), "قیمت")
    except ValueError as exc:
        return json_error(str(exc))

    if not title or not author or not genre or not condition or not address:
        return jsonify(error="لطفاً همه‌ی فیلدهای اجباری را پر کن."), 400
    if share_type not in SHARE_TYPES:
        share_type = "free"
    if share_type == "sale" and sale_price is None:
        return json_error("برای فروش، قیمت را وارد کنید.")
    if share_type == "deposit" and deposit_amount is None:
        return json_error("برای امانت با ودیعه، مبلغ ودیعه را وارد کنید.")
    if share_type in {"free", "deposit"} and duration is None:
        return json_error("مدت امانت را وارد کنید.")

    cover_filename = None
    file = request.files.get("cover")
    if file and file.filename:
        if not allowed_file(file.filename) or not (file.mimetype or "").startswith("image/") or not valid_image_upload(file):
            return json_error("فرمت جلد باید تصویر PNG، JPG، JPEG، WEBP یا GIF باشد.")
        ext = file.filename.rsplit(".", 1)[1].lower()
        cover_filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(COVERS_DIR, cover_filename))

    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            """INSERT INTO books
               (user_id, title, author, genre, book_condition, share_type,
                duration, deposit_amount, sale_price, address, description, cover)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                current_user_id(), title, author, genre, condition, share_type,
                duration or None, deposit_amount or None, sale_price or None,
                address, description, cover_filename,
            ),
        )
        db.commit()
        book_id = cur.lastrowid
        cur.close()
        db.close()
    except MySQLError as e:
        if cover_filename:
            try:
                os.remove(os.path.join(COVERS_DIR, cover_filename))
            except OSError:
                pass
        app.logger.exception("Book creation failed")
        return json_error("ثبت کتاب انجام نشد.", 503)

    book_row = {
        "id": book_id,
        "user_id": current_user_id(),
        "title": title,
        "author": author,
        "genre": genre,
        "book_condition": condition,
        "share_type": share_type,
        "duration": duration,
        "deposit_amount": deposit_amount,
        "sale_price": sale_price,
        "address": address,
        "description": description,
        "cover": cover_filename,
    }
    try:
        detail_url = generate_book_page(book_row, session.get("user_name", ""))
    except (OSError, ValueError, KeyError):
        app.logger.exception("Book page generation failed")
        try:
            with db_cursor() as (cleanup_db, cleanup_cur):
                cleanup_cur.execute("DELETE FROM books WHERE id=%s", (book_id,))
                cleanup_db.commit()
        except MySQLError:
            app.logger.exception("Could not roll back book after page generation failure")
        if cover_filename:
            try:
                os.remove(os.path.join(COVERS_DIR, cover_filename))
            except OSError:
                pass
        return json_error("صفحه‌ی کتاب ساخته نشد؛ دوباره تلاش کنید.", 503)

    return jsonify(success=True, id=book_id, detailUrl=detail_url)


@app.route("/api/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401

    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM books WHERE id=%s", (book_id,))
        book = cur.fetchone()

        if not book:
            cur.close()
            db.close()
            return jsonify(error="کتاب پیدا نشد."), 404

        is_owner = book["user_id"] == current_user_id()
        is_admin = bool(session.get("is_admin"))  # فعلاً همیشه False؛ برای آینده آماده است

        if not is_owner and not is_admin:
            cur.close()
            db.close()
            return jsonify(error="اجازه‌ی حذف این کتاب را نداری."), 403

        cur.execute("DELETE FROM books WHERE id=%s", (book_id,))
        db.commit()
        cur.close()
        db.close()
    except MySQLError as e:
        return jsonify(error=f"خطای دیتابیس: {e}"), 500

    if book.get("cover"):
        try:
            os.remove(os.path.join(COVERS_DIR, book["cover"]))
        except OSError:
            pass

    delete_book_page(book_id)

    return jsonify(success=True)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
