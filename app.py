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
import re
import uuid
import secrets
import time
from collections import defaultdict, deque
from threading import Lock
from html import escape
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from flask import Flask, request, jsonify, session, send_from_directory, render_template, abort, Response
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
MAX_UPLOADS_PER_HOUR = int(os.getenv("MAX_UPLOADS_PER_HOUR", "20"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
COVERS_DIR = os.path.join(BASE_DIR, "covers")
SAMPLE_BOOKS_DIR = os.path.join(TEMPLATES_DIR, "books")
# صفحه‌های تولیدشده هیچ‌وقت با Jinja رندر نمی‌شوند (محتوای کاربر داخلشان است)؛
# برای همین بیرون از پوشه‌ی templates و در یک پوشه‌ی مستقل ذخیره می‌شوند.
GENERATED_BOOKS_DIR = os.path.join(BASE_DIR, "pages")
TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, "_template.html")
os.makedirs(COVERS_DIR, exist_ok=True)
os.makedirs(GENERATED_BOOKS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
SHARE_TYPES = {"free", "deposit", "sale"}

# فهرست سفید صفحه‌های HTML؛ مسیر catch-all فقط همین‌ها را سرو می‌کند تا
# فایل‌هایی مثل app.py، schema.sql یا .env از بیرون قابل دانلود نباشند.
PAGE_TEMPLATES = {
    "index.html",
    "books.html",
    "upload.html",
    "login.html",
    "register.html",
    "process.html",
    "community.html",
    "about.html",
    "contact.html",
    "rules.html",
    "panel.html",
}
SAMPLE_BOOK_PAGE_RE = re.compile(r"^book\d+\.html$")
GENERATED_BOOK_PAGE_RE = re.compile(r"^book_\d+\.html$")
AMOUNT_MAX = 1_000_000_000
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

BOOK_REQUESTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS book_requests (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    book_id       INT NOT NULL,
    requester_id  INT NOT NULL,
    owner_id      INT NOT NULL,
    share_type    VARCHAR(20) NOT NULL DEFAULT 'free',
    amount        INT NULL,
    message       VARCHAR(500) NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_requests_owner_status (owner_id, status),
    INDEX idx_requests_requester (requester_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def ensure_schema():
    """جدول درخواست‌ها را در نصب‌های قدیمی هم می‌سازد (اجرای دوباره‌ی schema.sql لازم نیست)."""
    try:
        with db_cursor() as (db, cur):
            cur.execute(BOOK_REQUESTS_TABLE_SQL)
            db.commit()
    except MySQLError:
        app.logger.warning("Could not ensure book_requests table", exc_info=True)


@app.errorhandler(413)
def request_too_large(_error):
    return json_error("حجم فایل بیشتر از ۵ مگابایت است.", 413)


def wants_json():
    return request.path.startswith("/api/")


@app.errorhandler(404)
def not_found(_error):
    if wants_json():
        return json_error("مسیر موردنظر پیدا نشد.", 404)
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_error):
    if wants_json():
        return json_error("خطای داخلی سرور. دوباره تلاش کنید.", 500)
    return render_template("404.html", server_error=True), 500


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
    """کرسر بافر‌شده؛ نتایج بلافاصله خوانده می‌شوند تا بستن کرسر خطای
    «Unread result found» ندهد (این خطا باعث می‌شد /api/health همیشه ۵۰۳ بدهد).
    """
    db = get_db()
    cur = db.cursor(dictionary=dictionary, buffered=True)
    try:
        yield db, cur
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()
        db.close()


def json_error(message, status=400):
    return jsonify(error=message), status


def rate_limited(bucket, limit, window_seconds=300):
    """محدودکننده‌ی سبک برای جلوگیری از سوءاستفاده از endpointهای حساس."""
    now = time.monotonic()
    with RATE_LIMIT_LOCK:
        # جلوگیری از رشد بی‌نهایت دیکشنری وقتی درخواست‌ها از IPهای زیادی می‌آیند.
        if len(RATE_LIMIT_STORE) > 2048:
            for key in [k for k, v in RATE_LIMIT_STORE.items() if not v or now - v[-1] > 3600]:
                RATE_LIMIT_STORE.pop(key, None)
        events = RATE_LIMIT_STORE[bucket]
        while events and now - events[0] > window_seconds:
            events.popleft()
        if len(events) >= limit:
            return True
        events.append(now)
    return False


def request_bucket(prefix, value=""):
    return f"{prefix}:{request.remote_addr or 'unknown'}:{value}"


def parse_amount(value, label):
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
        if number < 0 or number > AMOUNT_MAX or number != number.to_integral_value():
            raise InvalidOperation
        return int(number)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label} باید یک عدد صحیح مثبت باشد.")


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


def rebuild_book_page(book_id):
    """اگر فایل صفحه‌ی کتاب گم شده ولی کتاب در دیتابیس هست، صفحه را دوباره می‌سازد."""
    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute(
                "SELECT books.*, users.name AS owner_name FROM books "
                "JOIN users ON books.user_id = users.id WHERE books.id=%s",
                (book_id,),
            )
            book = cur.fetchone()
    except MySQLError:
        app.logger.warning("Could not load book %s for page rebuild", book_id, exc_info=True)
        return False
    if not book:
        return False
    try:
        return bool(generate_book_page(book, book.get("owner_name") or ""))
    except OSError:
        app.logger.exception("Book page rebuild failed")
        return False


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


@app.route("/books/<path:filename>")
def serve_book_page(filename):
    """صفحه‌های کتاب: نمونه‌ها با Jinja، صفحه‌های ساخته‌شده به‌صورت فایل خام.

    صفحه‌های تولیدشده از روی قالب، عنوان/نویسنده/توضیح کاربر را داخل خود دارند؛
    اگر با render_template سرو شوند، Jinja دستورهای داخل محتوای کاربر را هم
    اجرا می‌کند (SSTI). پس فقط با send_from_directory فرستاده می‌شوند.
    """
    base = os.path.basename(filename)
    if base != filename:
        abort(404)
    if SAMPLE_BOOK_PAGE_RE.match(base):
        if not os.path.isfile(os.path.join(SAMPLE_BOOKS_DIR, base)):
            abort(404)
        return render_template(f"books/{base}")
    if GENERATED_BOOK_PAGE_RE.match(base):
        path = os.path.join(GENERATED_BOOKS_DIR, base)
        if not os.path.isfile(path):
            book_id = int(base[len("book_"):-len(".html")])
            if not rebuild_book_page(book_id):
                abort(404)
        # فایل در حافظه خوانده می‌شود تا هندل باز نماند و در ویندوز حذف فایل
        # بلافاصله بعد از دیده‌شدن صفحه شکست نخورد.
        with open(path, "r", encoding="utf-8") as handle:
            html = handle.read()
        return Response(html, mimetype="text/html")
    abort(404)


@app.route("/<path:filename>")
def serve_static_file(filename):
    """فقط صفحه‌های شناخته‌شده‌ی سایت؛ بقیه‌ی فایل‌های پروژه عمومی نیستند."""
    if filename in PAGE_TEMPLATES:
        return render_template(filename)
    abort(404)


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
            db.commit()
    except MySQLError as e:
        app.logger.exception("Registration failed")
        return json_error("ثبت‌نام انجام نشد. دوباره تلاش کنید.", 503)

    # بدون مرحله‌ی تأیید ایمیل، کاربر بلافاصله وارد حساب تازه‌اش می‌شود.
    session.clear()
    session["user_id"] = user_id
    session["user_name"] = name
    session["is_admin"] = False
    return jsonify(success=True, id=user_id, name=name)


@app.route("/api/login", methods=["POST"])
def login():
    if rate_limited(request_bucket("login"), 10):
        return json_error("تعداد تلاش‌های ورود زیاد است؛ چند دقیقه بعد دوباره امتحان کن.", 429)
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cur.fetchone()
    except MySQLError as e:
        app.logger.exception("Login failed")
        return json_error("ورود انجام نشد. دوباره تلاش کنید.", 503)

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="ایمیل یا رمز عبور اشتباه است."), 401

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["is_admin"] = bool(user.get("is_admin"))
    return jsonify(success=True, id=user["id"], name=user["name"])


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(success=True)


@app.route("/api/me")
def me():
    if not current_user_id():
        return jsonify(loggedIn=False)

    email = phone = None
    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute("SELECT name, email, phone FROM users WHERE id=%s", (current_user_id(),))
            user = cur.fetchone()
    except MySQLError:
        app.logger.exception("Loading current user failed")
        user = None

    name = user["name"] if user else session.get("user_name")
    if user:
        email = user["email"]
        phone = user["phone"]

    pending_requests = 0
    try:
        with db_cursor() as (_db, cur):
            cur.execute(
                "SELECT COUNT(*) FROM book_requests WHERE owner_id=%s AND status='pending'",
                (session["user_id"],),
            )
            row = cur.fetchone()
            pending_requests = int(row[0]) if row else 0
    except MySQLError:
        app.logger.warning("Pending request count failed", exc_info=True)

    return jsonify(
        loggedIn=True,
        id=session["user_id"],
        name=name,
        email=email,
        phone=phone,
        isAdmin=bool(session.get("is_admin")),
        pendingRequests=pending_requests,
    )


@app.route("/api/profile", methods=["POST"])
def update_profile():
    """ویرایش نام و شماره موبایل از پنل کاربری."""
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401
    if rate_limited(request_bucket("profile", str(current_user_id())), 20, 3600):
        return json_error("تعداد ویرایش‌ها زیاد است؛ کمی بعد دوباره تلاش کن.", 429)

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not 2 <= len(name) <= 255:
        return json_error("نام باید بین ۲ تا ۲۵۵ نویسه باشد.")
    if phone and not re.fullmatch(r"09\d{9}", phone):
        return json_error("شماره موبایل باید با ۰۹ شروع شود و ۱۱ رقم باشد.")

    try:
        with db_cursor() as (db, cur):
            cur.execute(
                "UPDATE users SET name=%s, phone=%s WHERE id=%s",
                (name, phone or None, current_user_id()),
            )
            db.commit()
    except MySQLError:
        app.logger.exception("Profile update failed")
        return json_error("ذخیره‌ی اطلاعات انجام نشد. دوباره تلاش کنید.", 503)

    session["user_name"] = name
    return jsonify(success=True, name=name, phone=phone)


@app.route("/api/password", methods=["POST"])
def change_password():
    """تغییر رمز عبور از پنل کاربری؛ رمز فعلی باید تأیید شود."""
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401
    if rate_limited(request_bucket("password", str(current_user_id())), 5, 900):
        return json_error("تعداد تلاش برای تغییر رمز زیاد است؛ ۱۵ دقیقه بعد دوباره امتحان کن.", 429)

    data = request.get_json(silent=True) or {}
    current_password = data.get("currentPassword") or ""
    new_password = data.get("newPassword") or ""

    if len(new_password) < 8:
        return json_error("رمز جدید باید حداقل ۸ نویسه باشد.")
    if new_password == current_password:
        return json_error("رمز جدید باید با رمز فعلی فرق کند.")

    user_id = current_user_id()
    user_name = session.get("user_name")
    is_admin = bool(session.get("is_admin"))

    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute("SELECT password_hash FROM users WHERE id=%s", (user_id,))
            user = cur.fetchone()
            if not user or not check_password_hash(user["password_hash"], current_password):
                return json_error("رمز فعلی درست نیست.", 403)

            cur.execute(
                "UPDATE users SET password_hash=%s WHERE id=%s",
                (generate_password_hash(new_password), user_id),
            )
            db.commit()
    except MySQLError:
        app.logger.exception("Password change failed")
        return json_error("تغییر رمز انجام نشد. دوباره تلاش کنید.", 503)

    # نشست را با همان کاربر دوباره می‌سازیم تا نشانه‌های قبلی پاک شوند.
    session.clear()
    session["user_id"] = user_id
    session["user_name"] = user_name
    session["is_admin"] = is_admin
    return jsonify(success=True)


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

    db = get_db()
    try:
        cur = db.cursor()
        try:
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
        finally:
            cur.close()
    except MySQLError:
        if cover_filename:
            try:
                os.remove(os.path.join(COVERS_DIR, cover_filename))
            except OSError:
                pass
        app.logger.exception("Book creation failed")
        return json_error("ثبت کتاب انجام نشد.", 503)
    finally:
        # اتصال در هر مسیری (موفق یا خطا) به استخر برگردانده می‌شود.
        db.close()

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

    db = get_db()
    try:
        cur = db.cursor(dictionary=True)
        try:
            cur.execute("SELECT * FROM books WHERE id=%s", (book_id,))
            book = cur.fetchone()

            if not book:
                return jsonify(error="کتاب پیدا نشد."), 404

            is_owner = book["user_id"] == current_user_id()
            is_admin = bool(session.get("is_admin"))  # فعلاً همیشه False؛ برای آینده آماده است

            if not is_owner and not is_admin:
                return jsonify(error="اجازه‌ی حذف این کتاب را نداری."), 403

            cur.execute("DELETE FROM books WHERE id=%s", (book_id,))
            db.commit()
        finally:
            cur.close()
    except MySQLError:
        # جزئیات خطای دیتابیس فقط در لاگ می‌ماند و به کاربر نشان داده نمی‌شود.
        app.logger.exception("Book deletion failed")
        return json_error("حذف کتاب انجام نشد. دوباره تلاش کنید.", 503)
    finally:
        db.close()

    if book.get("cover"):
        try:
            os.remove(os.path.join(COVERS_DIR, book["cover"]))
        except OSError:
            pass

    delete_book_page(book_id)

    return jsonify(success=True)


# ---------- درخواست‌های امانت / خرید ----------
REQUEST_STATUSES = {"pending", "accepted", "rejected", "cancelled"}
REQUEST_STATUS_LABELS = {
    "pending": "در انتظار پاسخ",
    "accepted": "تأیید شد",
    "rejected": "رد شد",
    "cancelled": "لغو شد",
}


def request_to_dict(row):
    return {
        "id": row["id"],
        "bookId": row["book_id"],
        "bookTitle": row["book_title"],
        "bookDetailUrl": f"/books/book_{row['book_id']}.html",
        "shareType": row["share_type"],
        "shareTypeLabel": SHARE_TYPE_BADGE_LABELS.get(row["share_type"], row["share_type"]),
        "amount": row["amount"],
        "message": row["message"],
        "status": row["status"],
        "statusLabel": REQUEST_STATUS_LABELS.get(row["status"], row["status"]),
        "requesterId": row["requester_id"],
        "requesterName": row.get("requester_name"),
        "ownerId": row["owner_id"],
        "ownerName": row.get("owner_name"),
        "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
        "canRespond": row["owner_id"] == current_user_id() and row["status"] == "pending",
        "canCancel": row["requester_id"] == current_user_id() and row["status"] == "pending",
    }


def load_requests(box):
    """درخواست‌های دریافتی (box='incoming') یا ارسالی (box='outgoing') کاربر فعلی."""
    if box == "incoming":
        where, param = "r.owner_id=%s", current_user_id()
    else:
        where, param = "r.requester_id=%s", current_user_id()

    with db_cursor(dictionary=True) as (_db, cur):
        cur.execute(
            f"""SELECT r.*, b.title AS book_title,
                       requester.name AS requester_name,
                       owner.name AS owner_name
                FROM book_requests r
                JOIN books b ON b.id = r.book_id
                JOIN users requester ON requester.id = r.requester_id
                JOIN users owner ON owner.id = r.owner_id
                WHERE {where}
                ORDER BY (r.status = 'pending') DESC, r.created_at DESC
                LIMIT 100""",
            (param,),
        )
        return cur.fetchall()


@app.route("/api/requests", methods=["GET"])
def list_requests():
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401

    try:
        incoming = load_requests("incoming")
        outgoing = load_requests("outgoing")
    except MySQLError:
        app.logger.exception("Request listing failed")
        return json_error("دریافت درخواست‌ها انجام نشد.", 503)

    return jsonify(
        incoming=[request_to_dict(row) for row in incoming],
        outgoing=[request_to_dict(row) for row in outgoing],
        pendingIncoming=sum(1 for row in incoming if row["status"] == "pending"),
        pendingOutgoing=sum(1 for row in outgoing if row["status"] == "pending"),
    )


@app.route("/api/books/<int:book_id>/requests", methods=["POST"])
def create_request(book_id):
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401
    if rate_limited(request_bucket("request", str(current_user_id())), 20, 3600):
        return json_error("تعداد درخواست‌هایت زیاد است؛ کمی بعد دوباره تلاش کن.", 429)

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if len(message) > 500:
        return json_error("متن پیام حداکثر ۵۰۰ نویسه می‌تواند باشد.")

    db = get_db()
    try:
        cur = db.cursor(dictionary=True, buffered=True)
        try:
            cur.execute(
                "SELECT id, user_id, title, share_type, deposit_amount, sale_price FROM books WHERE id=%s",
                (book_id,),
            )
            book = cur.fetchone()
            if not book:
                return jsonify(error="کتاب پیدا نشد."), 404
            if book["user_id"] == current_user_id():
                return json_error("این کتاب خودت است؛ نمی‌توانی برای آن درخواست بدهی.")

            cur.execute(
                "SELECT id FROM book_requests WHERE book_id=%s AND requester_id=%s AND status='pending'",
                (book_id, current_user_id()),
            )
            if cur.fetchone():
                return json_error("قبلاً برای این کتاب درخواست داده‌ای؛ منتظر پاسخ صاحب کتاب باش.", 409)

            amount = book["deposit_amount"] if book["share_type"] == "deposit" else book["sale_price"]
            cur.execute(
                """INSERT INTO book_requests
                   (book_id, requester_id, owner_id, share_type, amount, message, status)
                   VALUES (%s, %s, %s, %s, %s, %s, 'pending')""",
                (book_id, current_user_id(), book["user_id"], book["share_type"], amount, message or None),
            )
            db.commit()
            request_id = cur.lastrowid
        finally:
            cur.close()
    except MySQLError:
        app.logger.exception("Request creation failed")
        return json_error("ثبت درخواست انجام نشد. دوباره تلاش کنید.", 503)
    finally:
        db.close()

    return jsonify(success=True, id=request_id, bookTitle=book["title"], status="pending")


@app.route("/api/requests/<int:request_id>/status", methods=["POST"])
def update_request_status(request_id):
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401

    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()
    if new_status not in REQUEST_STATUSES:
        return json_error("وضعیت درخواست معتبر نیست.")

    db = get_db()
    try:
        cur = db.cursor(dictionary=True, buffered=True)
        try:
            cur.execute(
                "SELECT id, book_id, requester_id, owner_id, status FROM book_requests WHERE id=%s",
                (request_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify(error="درخواست پیدا نشد."), 404

            # اول دسترسی، بعد وضعیت؛ تا کاربر بیگانه از حالت درخواست خبردار نشود.
            is_owner = row["owner_id"] == current_user_id()
            is_requester = row["requester_id"] == current_user_id()

            if not is_owner and not is_requester:
                return jsonify(error="به این درخواست دسترسی نداری."), 403
            if new_status in {"accepted", "rejected"} and not is_owner:
                return jsonify(error="فقط صاحب کتاب می‌تواند این درخواست را تأیید یا رد کند."), 403
            if new_status == "cancelled" and not is_requester:
                return jsonify(error="فقط فرستنده‌ی درخواست می‌تواند آن را لغو کند."), 403
            if row["status"] != "pending":
                return json_error("این درخواست قبلاً بررسی شده است.", 409)

            cur.execute(
                "UPDATE book_requests SET status=%s WHERE id=%s",
                (new_status, request_id),
            )

            # با تأیید یک درخواست، بقیه‌ی درخواست‌های همان کتاب خودکار رد می‌شوند.
            if new_status == "accepted":
                cur.execute(
                    """UPDATE book_requests SET status='rejected'
                       WHERE book_id=%s AND status='pending' AND id<>%s""",
                    (row["book_id"], request_id),
                )

            db.commit()
        finally:
            cur.close()
    except MySQLError:
        app.logger.exception("Request status update failed")
        return json_error("تغییر وضعیت درخواست انجام نشد.", 503)
    finally:
        db.close()

    return jsonify(success=True, id=request_id, status=new_status, statusLabel=REQUEST_STATUS_LABELS[new_status])


# جدول درخواست‌ها در اولین اجرا (یا نصب‌های قدیمی) ساخته می‌شود.
ensure_schema()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)