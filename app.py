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
from functools import wraps
from datetime import date, datetime, timedelta
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
    "admin.html",
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
    delivered_at  DATETIME NULL,
    due_at        DATE NULL,
    returned_at   DATETIME NULL,
    completed_at  DATETIME NULL,
    reminder_sent TINYINT(1) NOT NULL DEFAULT 0,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_requests_owner_status (owner_id, status),
    INDEX idx_requests_requester (requester_id, status),
    INDEX idx_requests_due (status, due_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

NOTIFICATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS notifications (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    type        VARCHAR(30) NOT NULL,
    title       VARCHAR(255) NOT NULL,
    body        VARCHAR(500) NULL,
    link        VARCHAR(255) NULL,
    is_read     TINYINT(1) NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notifications_user (user_id, is_read, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

FAVORITES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS favorites (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    book_id     INT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_favorite (user_id, book_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

REVIEWS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS reviews (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    book_id     INT NOT NULL,
    user_id     INT NOT NULL,
    request_id  INT NULL,
    rating      TINYINT NOT NULL,
    comment     VARCHAR(700) NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_review (book_id, user_id),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES book_requests(id) ON DELETE SET NULL,
    INDEX idx_reviews_book (book_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# ستون‌هایی که در نصب‌های قدیمی جدول درخواست‌ها وجود ندارند و باید اضافه شوند.
REQUEST_COLUMN_MIGRATIONS = {
    "delivered_at": "ALTER TABLE book_requests ADD COLUMN delivered_at DATETIME NULL",
    "due_at": "ALTER TABLE book_requests ADD COLUMN due_at DATE NULL",
    "returned_at": "ALTER TABLE book_requests ADD COLUMN returned_at DATETIME NULL",
    "completed_at": "ALTER TABLE book_requests ADD COLUMN completed_at DATETIME NULL",
    "reminder_sent": "ALTER TABLE book_requests ADD COLUMN reminder_sent TINYINT(1) NOT NULL DEFAULT 0",
    "updated_at": (
        "ALTER TABLE book_requests ADD COLUMN updated_at TIMESTAMP "
        "NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    ),
}


USER_COLUMN_MIGRATIONS = {
    "last_login_at": "ALTER TABLE users ADD COLUMN last_login_at DATETIME NULL",
    "login_count": "ALTER TABLE users ADD COLUMN login_count INT NOT NULL DEFAULT 0",
}


def ensure_column(cur, table, column, ddl):
    """ستون را فقط اگر وجود نداشته باشد اضافه می‌کند (MySQL دستور IF NOT EXISTS ندارد)."""
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (table, column),
    )
    row = cur.fetchone()
    if row and int(row[0]) == 0:
        cur.execute(ddl)


def ensure_schema():
    """جدول‌های تازه را در نصب‌های قدیمی هم می‌سازد (اجرای دوباره‌ی schema.sql لازم نیست)."""
    try:
        with db_cursor() as (db, cur):
            cur.execute(BOOK_REQUESTS_TABLE_SQL)
            for column, ddl in REQUEST_COLUMN_MIGRATIONS.items():
                ensure_column(cur, "book_requests", column, ddl)
            for column, ddl in USER_COLUMN_MIGRATIONS.items():
                ensure_column(cur, "users", column, ddl)
            cur.execute(NOTIFICATIONS_TABLE_SQL)
            cur.execute(FAVORITES_TABLE_SQL)
            cur.execute(REVIEWS_TABLE_SQL)
            db.commit()
    except MySQLError:
        app.logger.warning("Could not ensure database schema", exc_info=True)


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
    rating_avg = row.get("rating_avg")
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
        "ratingAvg": round(float(rating_avg), 1) if rating_avg is not None else None,
        "ratingCount": int(row.get("rating_count") or 0),
        "isFavorite": bool(row.get("is_favorite")),
    }


# ستون‌های تکمیلی که همراه هر کوئری کتاب خوانده می‌شوند تا امتیاز و علاقه‌مندی
# در فهرست‌ها هم بدون کوئری اضافه در دسترس باشد.
BOOK_ENRICH_COLUMNS = """
        (SELECT AVG(rv.rating) FROM reviews rv WHERE rv.book_id = books.id) AS rating_avg,
        (SELECT COUNT(*) FROM reviews rv WHERE rv.book_id = books.id) AS rating_count,
        EXISTS(SELECT 1 FROM favorites f WHERE f.book_id = books.id AND f.user_id = %s) AS is_favorite
"""


SHARE_TYPE_BADGE_LABELS = {"free": "امانت رایگان", "deposit": "امانت با ودیعه", "sale": "فروش"}
GENRE_LABELS = {
    "novel": "رمان", "story": "داستان کوتاه", "poetry": "شعر و ادبیات",
    "history": "تاریخ", "science": "علمی", "kids": "کودک و نوجوان", "other": "سایر",
}
CONDITION_LABELS = {"new": "نو", "like-new": "در حد نو", "good": "قابل قبول"}
FA_DIGITS_TABLE = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_fa(value):
    """ارقام لاتین را برای نمایش به فارسی تبدیل می‌کند."""
    return str(value).translate(FA_DIGITS_TABLE)


def build_request_rows_html(book):
    rows = []
    if book["share_type"] in ("free", "deposit") and book.get("duration"):
        rows.append(
            '<div class="request-row"><span>مهلت امانت</span><span>'
            + to_fa(book["duration"]) + " روز</span></div>"
        )
    if book["share_type"] == "deposit" and book.get("deposit_amount"):
        deposit = to_fa("{:,}".format(book["deposit_amount"]))
        rows.append(
            '<div class="request-row"><span>مبلغ ودیعه</span><span>'
            + deposit + " تومان</span></div>"
        )
    if book["share_type"] == "sale" and book.get("sale_price"):
        price = to_fa("{:,}".format(book["sale_price"]))
        rows.append(
            '<div class="request-row"><span>قیمت</span><span>'
            + price + " تومان</span></div>"
        )
    return "\n".join(rows)


def build_steps_html(book):
    """سه قدم امانت/خرید برای ستون معرفی صفحه‌ی کتاب."""
    is_sale = book["share_type"] == "sale"
    steps = [
        ("درخواست بده", 'روی دکمه‌ی درخواست بزن تا پیام برای صاحب کتاب برود.'),
        ("هماهنگی کن", "بعد از تأیید، زمان و محل تحویل را در پنل هماهنگ کنید."),
    ]
    if is_sale:
        steps.append(("تحویل بگیر", "صاحب کتاب تحویل را ثبت می‌کند و خریدار دریافت را تأیید می‌کند."))
    else:
        steps.append(("بخوان و برگردان", "در پایان، بازگشت کتاب را ثبت کن و امتیاز و نظرت را بنویس."))

    nums = ["۱", "۲", "۳"]
    items = []
    for index, (title, text) in enumerate(steps):
        items.append(
            '<li><span class="step-num">' + nums[index] + "</span>"
            + '<div><strong>' + title + "</strong><p>" + text + "</p></div></li>"
        )
    return "\n".join(items)


def book_facts(book):
    """(برچسب، مقدار) برای ردیف مدت/قیمت در مشخصات کتاب."""
    if book["share_type"] == "sale":
        price = book.get("sale_price")
        return "قیمت", (to_fa("{:,}".format(price)) + " تومان") if price else "—"
    duration = book.get("duration")
    return "مدت امانت", (to_fa(duration) + " روز") if duration else "—"


def generate_book_page(book, owner_name):
    """از روی قالب books/_template.html، صفحه‌ی اختصاصیِ کتاب را می‌سازد."""
    if not os.path.exists(TEMPLATE_PATH):
        return  # قالب موجود نیست؛ صفحه ساخته نمی‌شود ولی بقیه‌ی سیستم کار می‌کند

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    cover_src = f"/covers/{book['cover']}" if book.get("cover") else "/static/images/logo.png"
    request_btn_label = "خرید می‌کنم" if book["share_type"] == "sale" else "امانت می‌گیرم"
    fact_label, fact_value = book_facts(book)

    replacements = {
        "__TITLE__": escape(str(book["title"])),
        "__AUTHOR__": escape(str(book["author"])),
        "__GENRE__": escape(GENRE_LABELS.get(book["genre"], str(book["genre"]))),
        "__GENRE_VALUE__": escape(str(book["genre"])),
        "__CONDITION__": escape(CONDITION_LABELS.get(book["book_condition"], str(book["book_condition"]))),
        "__ADDRESS__": escape(str(book["address"])),
        "__DESCRIPTION__": escape(str(book.get("description") or "")).replace("\n", "<br>") ,
        "__OWNER_NAME__": escape(str(owner_name)),
        "__OWNER_INITIAL__": escape((str(owner_name).strip()[:1] or "؟")),
        "__OWNER_ID__": str(book["user_id"]),
        "__BOOK_ID__": str(book["id"]),
        "__COVER_SRC__": cover_src,
        "__BADGE_CLASS__": book["share_type"],
        "__BADGE_LABEL__": SHARE_TYPE_BADGE_LABELS.get(book["share_type"], book["share_type"]),
        "__REQUEST_ROWS__": build_request_rows_html(book),
        "__REQUEST_BTN_LABEL__": request_btn_label,
        "__STEPS__": build_steps_html(book),
        "__FACT_LABEL__": escape(fact_label),
        "__FACT_VALUE__": escape(fact_value),
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


def book_page_is_stale(book_id):
    """صفحه‌ی ذخیره‌شده قدیمی‌تر از قالب است؟ (یعنی قالب بعد از ساخت صفحه عوض شده)"""
    page_path = os.path.join(GENERATED_BOOKS_DIR, f"book_{book_id}.html")
    try:
        return os.path.getmtime(page_path) < os.path.getmtime(TEMPLATE_PATH)
    except OSError:
        return False


# ---------- کتاب‌های نمونه (داده‌ی اولیه) ----------
# این کتاب‌ها قبلاً فقط کارت‌های ثابتِ books.html بودند و صفحه‌شان چیزی مثل
# «علاقه‌مندی» یا درخواست واقعی نداشت. حالا یک‌بار در دیتابیس ثبت می‌شوند تا
# صفحه‌ی واقعی، قلب علاقه‌مندی، درخواست و امتیاز داشته باشند.
DEMO_USER_EMAIL = "demo@ketab-beketab.local"
DEMO_ADDRESS = "تهران، علامه‌حلی ۲"
DEMO_BOOKS = [
    {
        "title": "هری پاتر و سنگ جادو", "author": "جی.کی.رولینگ", "genre": "kids",
        "book_condition": "like-new", "share_type": "free", "duration": 14,
        "cover": "3a604bbbf5d5e636edec4f5a33f61bc40b7c8c73_1684874096.jpg",
        "description": "جلد اول ماجراهای هری پاتر؛ نسخه‌ی فارسی با جلد سالم و بدون خط‌خوردگی.",
    },
    {
        "title": "بیست‌هزار فرسنگ زیر دریا", "author": "ژول ورن", "genre": "novel",
        "book_condition": "good", "share_type": "free", "duration": 14,
        "cover": "20000-farsang.jpg",
        "description": "سفرنامه‌ی خیالی ناخدا نمو؛ ترجمه‌ی روان و کاغذ سالم.",
    },
    {
        "title": "الیور تویست", "author": "چارلز دیکنز", "genre": "novel",
        "book_condition": "good", "share_type": "deposit", "duration": 14, "deposit_amount": 100000,
        "cover": "oliver-twist.jpg",
        "description": "رمان کلاسیک دیکنز درباره‌ی کودکی در لندن قرن نوزدهم. ودیعه بعد از بازگشت سالم کتاب برمی‌گردد.",
    },
    {
        "title": "باهوش", "author": "کیم اسلیتر", "genre": "kids",
        "book_condition": "like-new", "share_type": "sale", "sale_price": 120000,
        "cover": "bahosh.jpg",
        "description": "کتاب کودک و نوجوان با تصویرگری رنگی؛ فروش به‌صورت قطعی.",
    },
    {
        "title": "کلیله و دمنه", "author": "نصرالله منشی", "genre": "story",
        "book_condition": "good", "share_type": "free", "duration": 10,
        "cover": "kelileh.jpg",
        "description": "قصه‌های آموزنده‌ی کلاسیک فارسی؛ مناسب مطالعه‌ی آرام و چندباره.",
    },
    {
        "title": "شازده‌کوچولو", "author": "آنتوان دو سنت اگزوپری", "genre": "kids",
        "book_condition": "like-new", "share_type": "free", "duration": 10,
        "cover": "shazde-koochooloo.jpg",
        "description": "نسخه‌ی جیبی با تصویرهای اصلی نویسنده.",
    },
    {
        "title": "صد سال تنهایی", "author": "گابریل گارسیا مارکز", "genre": "novel",
        "book_condition": "good", "share_type": "sale", "sale_price": 150000,
        "cover": "sad-sal-tanhaei.jpg",
        "description": "رمان مشهور مارکز؛ ترجمه‌ی کامل، بدون پارگی و یادداشت.",
    },
    {
        "title": "مدیر مدرسه", "author": "جلال آل‌احمد", "genre": "novel",
        "book_condition": "good", "share_type": "free", "duration": 14,
        "cover": "modir-madrese.jpg",
        "description": "داستان بلند آل‌احمد با لحن طنز و انتقادی؛ نسخه‌ی قدیمی اما سالم.",
    },
    {
        "title": "ارباب حلقه‌ها", "author": "جی.آر.آر. تالکین", "genre": "novel",
        "book_condition": "like-new", "share_type": "deposit", "duration": 21, "deposit_amount": 200000,
        "cover": "arbab-halgheha.jpg",
        "description": "سه‌گانه‌ی کامل در یک جلد؛ سنگین است، با احتیاط جابه‌جا شود.",
    },
    {
        "title": "داستان‌های شاهنامه برای نوجوانان", "author": "حسین جعفری", "genre": "kids",
        "book_condition": "like-new", "share_type": "free", "duration": 14,
        "cover": "shahnameh-teen.jpg",
        "description": "بازنویسی ساده و مصور چند داستان شاهنامه برای نوجوانان.",
    },
]


def seed_demo_books():
    """کتاب‌های نمونه را یک‌بار در دیتابیس ثبت می‌کند (با SEED_DEMO_BOOKS=0 خاموش می‌شود)."""
    if os.getenv("SEED_DEMO_BOOKS", "1") != "1":
        return
    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute("SELECT id FROM users WHERE email=%s", (DEMO_USER_EMAIL,))
            if cur.fetchone():
                return  # قبلاً یک‌بار ثبت شده است

            # اگر DEMO_PASSWORD تنظیم شده باشد، می‌توان با این حساب وارد شد و
            # درخواست‌های کتاب‌های نمونه را مدیریت کرد؛ وگرنه رمز تصادفی است.
            demo_password = os.getenv("DEMO_PASSWORD") or secrets.token_hex(24)
            cur.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                ("کتاب‌به‌کتاب (کتابخانه‌ی نمونه)", DEMO_USER_EMAIL,
                 generate_password_hash(demo_password)),
            )
            owner_id = cur.lastrowid
            db.commit()
    except MySQLError:
        app.logger.warning("Could not seed demo books", exc_info=True)
        return

    created = []
    for data in DEMO_BOOKS:
        try:
            with db_cursor(dictionary=True) as (db, cur):
                cur.execute(
                    """INSERT INTO books
                       (user_id, title, author, genre, book_condition, share_type,
                        duration, deposit_amount, sale_price, address, description, cover)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        owner_id, data["title"], data["author"], data["genre"], data["book_condition"],
                        data["share_type"], data.get("duration"), data.get("deposit_amount"),
                        data.get("sale_price"), DEMO_ADDRESS, data.get("description"),
                        data.get("cover"),
                    ),
                )
                db.commit()
                book_id = cur.lastrowid
        except MySQLError:
            app.logger.warning("Demo book insert failed: %s", data.get("title"), exc_info=True)
            continue

        row = dict(data)
        row["id"] = book_id
        row["user_id"] = owner_id
        row["address"] = DEMO_ADDRESS
        created.append(row)

    for row in created:
        try:
            generate_book_page(row, "کتاب‌به‌کتاب (کتابخانه‌ی نمونه)")
        except (OSError, ValueError, KeyError):
            app.logger.warning("Demo book page generation failed", exc_info=True)

    if created:
        app.logger.info("Seeded %s demo books", len(created))


# ---------- سرو کردن فایل‌های استاتیک سایت ----------
NOTIFICATION_WIDGET_TAG = '<script src="/static/js/notifications.js" defer></script>'


def with_notification_widget(html):
    """زنگ اعلان را به صفحه‌های کتاب (نمونه و تولیدشده) تزریق می‌کند.

    صفحه‌های تولیدشده فایل ثابت‌اند و از قبل ساخته شده‌اند؛ تزریق در زمان سرو
    باعث می‌شود بدون بازسازی همه‌ی فایل‌ها، همه‌ی صفحه‌ها زنگ اعلان داشته باشند.
    """
    if NOTIFICATION_WIDGET_TAG in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", f"    {NOTIFICATION_WIDGET_TAG}\n</body>", 1)
    return html


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
        return Response(with_notification_widget(render_template(f"books/{base}")), mimetype="text/html")
    if GENERATED_BOOK_PAGE_RE.match(base):
        path = os.path.join(GENERATED_BOOKS_DIR, base)
        book_id = int(base[len("book_"):-len(".html")])
        # اگر فایل نباشد یا قالب بعد از ساخت صفحه عوض شده باشد، از نو ساخته می‌شود
        # (وگرنه صفحه‌های قدیمی دکمه‌های تازه مثل قلب علاقه‌مندی را ندارند).
        if not os.path.isfile(path) or book_page_is_stale(book_id):
            if not rebuild_book_page(book_id):
                if not os.path.isfile(path):
                    abort(404)
        # فایل در حافظه خوانده می‌شود تا هندل باز نماند و در ویندوز حذف فایل
        # بلافاصله بعد از دیده‌شدن صفحه شکست نخورد.
        with open(path, "r", encoding="utf-8") as handle:
            html = handle.read()
        return Response(with_notification_widget(html), mimetype="text/html")
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

    # ثبت آخرین ورود برای پنل مدیریت («چه کسانی وارد شده‌اند»)
    try:
        with db_cursor() as (login_db, login_cur):
            login_cur.execute(
                "UPDATE users SET last_login_at=NOW(), login_count=login_count+1 WHERE id=%s",
                (user["id"],),
            )
            login_db.commit()
    except MySQLError:
        app.logger.warning("Could not record login time", exc_info=True)

    return jsonify(success=True, id=user["id"], name=user["name"], isAdmin=bool(user.get("is_admin")))


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

    if not user:
        # کاربر حذف شده است؛ نشست نباید معتبر بماند.
        session.clear()
        return jsonify(loggedIn=False)

    name = user["name"]
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

    unread_notifications = 0
    try:
        with db_cursor() as (_db, cur):
            cur.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id=%s AND is_read=0",
                (session["user_id"],),
            )
            row = cur.fetchone()
            unread_notifications = int(row[0]) if row else 0
    except MySQLError:
        app.logger.warning("Unread notification count failed", exc_info=True)

    return jsonify(
        loggedIn=True,
        id=session["user_id"],
        name=name,
        email=email,
        phone=phone,
        isAdmin=bool(session.get("is_admin")),
        pendingRequests=pending_requests,
        unreadNotifications=unread_notifications,
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
            query = f"""SELECT books.*, users.name AS owner_name, {BOOK_ENRICH_COLUMNS}
                       FROM books
                       JOIN users ON books.user_id = users.id"""
            params = [current_user_id() or 0]
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
                f"""SELECT books.*, users.name AS owner_name, {BOOK_ENRICH_COLUMNS}
                   FROM books JOIN users ON books.user_id = users.id
                   WHERE books.user_id=%s ORDER BY books.created_at DESC""",
                (current_user_id(), current_user_id()),
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
# چرخه‌ی کامل امانت:  در انتظار → تأیید → هماهنگی → تحویل → در حال امانت → بازگشت
# چرخه‌ی خرید:        در انتظار → تأیید → هماهنگی → تحویل → تکمیل
REQUEST_STATUSES = {
    "pending", "accepted", "coordinating", "delivered",
    "on_loan", "returned", "completed", "rejected", "cancelled",
}
REQUEST_STATUS_LABELS = {
    "pending": "در انتظار پاسخ",
    "accepted": "تأیید شد",
    "coordinating": "در حال هماهنگی",
    "delivered": "تحویل‌شده",
    "on_loan": "در حال امانت",
    "returned": "بازگشت داده شد",
    "completed": "خرید تکمیل شد",
    "rejected": "رد شد",
    "cancelled": "لغو شد",
}

# هر وضعیت از چه وضعیت‌هایی و توسط چه کسی قابل ثبت است.
# actor: owner (صاحب کتاب) | requester (درخواست‌دهنده) | both
REQUEST_TRANSITIONS = {
    "accepted":     ({"pending"}, "owner"),
    "rejected":     ({"pending"}, "owner"),
    "coordinating": ({"accepted"}, "both"),
    "delivered":    ({"coordinating"}, "owner"),
    "on_loan":      ({"delivered"}, "requester"),   # فقط برای امانت
    "completed":    ({"delivered"}, "requester"),   # فقط برای فروش
    "returned":     ({"on_loan"}, "owner"),
    "cancelled":    ({"pending", "accepted", "coordinating"}, "requester"),
}

LOAN_STEPS = ["accepted", "coordinating", "delivered", "on_loan", "returned"]
SALE_STEPS = ["accepted", "coordinating", "delivered", "completed"]
DUE_SOON_DAYS = 3


def request_role(row):
    """نقش کاربر فعلی در این درخواست: owner | requester | None"""
    user_id = current_user_id()
    if row["owner_id"] == user_id:
        return "owner"
    if row["requester_id"] == user_id:
        return "requester"
    return None


def available_actions(row):
    """دکمه‌هایی که کاربر فعلی در این مرحله می‌تواند بزند."""
    role = request_role(row)
    if not role:
        return []

    labels = {
        "accepted": ("تأیید", "accept"),
        "rejected": ("رد", "reject"),
        "coordinating": ("شروع هماهنگی", "step"),
        "delivered": ("ثبت تحویل", "step"),
        "on_loan": ("کتاب را دریافت کردم", "step"),
        "completed": ("دریافت کردم", "step"),
        "returned": ("کتاب برگشت", "step"),
        "cancelled": ("لغو درخواست", "ghost"),
    }
    is_sale = row["share_type"] == "sale"
    actions = []
    for status, (sources, actor) in REQUEST_TRANSITIONS.items():
        if row["status"] not in sources:
            continue
        if actor != "both" and actor != role:
            continue
        # «در حال امانت» مخصوص امانت و «تکمیل» مخصوص فروش است.
        if status == "on_loan" and is_sale:
            continue
        if status == "completed" and not is_sale:
            continue
        label, style = labels[status]
        actions.append({"status": status, "label": label, "style": style})
    return actions


def request_to_dict(row):
    role = request_role(row)
    steps = SALE_STEPS if row["share_type"] == "sale" else LOAN_STEPS
    current_step = steps.index(row["status"]) + 1 if row["status"] in steps else 0

    due_at = row.get("due_at")
    days_left = None
    if due_at:
        days_left = (due_at - date.today()).days

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
        "steps": steps,
        "currentStep": current_step,
        "isActiveLoan": row["status"] in {"delivered", "on_loan"},
        "requesterId": row["requester_id"],
        "requesterName": row.get("requester_name"),
        "ownerId": row["owner_id"],
        "ownerName": row.get("owner_name"),
        "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
        "deliveredAt": row["delivered_at"].isoformat() if row.get("delivered_at") else None,
        "dueAt": due_at.isoformat() if due_at else None,
        "returnedAt": row["returned_at"].isoformat() if row.get("returned_at") else None,
        "daysLeft": days_left,
        "isOverdue": days_left is not None and days_left < 0 and row["status"] == "on_loan",
        "role": role,
        "actions": available_actions(row),
        "canRespond": role == "owner" and row["status"] == "pending",
        "canCancel": role == "requester" and row["status"] == "pending",
    }


# ---------- اعلان‌های داخل سایت ----------
def push_notification(cur, user_id, ntype, title, body=None, link=None):
    """اعلان را در همان تراکنش جاری ثبت می‌کند (بدون commit)."""
    if not user_id:
        return
    cur.execute(
        "INSERT INTO notifications (user_id, type, title, body, link) VALUES (%s, %s, %s, %s, %s)",
        (user_id, ntype, title[:255], (body or "")[:500] or None, (link or "")[:255] or None),
    )


def notify_status_change(cur, row, new_status, book_title):
    """طرف مقابل را از تغییر وضعیت درخواست باخبر می‌کند."""
    labels = REQUEST_STATUS_LABELS
    requester_id, owner_id = row["requester_id"], row["owner_id"]
    link = "/panel.html#loans"

    if new_status == "accepted":
        push_notification(
            cur, requester_id, "request_status",
            f"درخواست «{book_title}» تأیید شد",
            "صاحب کتاب درخواستت را پذیرفت. برای هماهنگی تحویل به پنل سر بزن.", link,
        )
    elif new_status == "rejected":
        push_notification(
            cur, requester_id, "request_status",
            f"درخواست «{book_title}» رد شد",
            "صاحب کتاب این درخواست را نپذیرفت.", link,
        )
    elif new_status == "coordinating":
        target = owner_id if row["requester_id"] == current_user_id() else requester_id
        push_notification(
            cur, target, "request_status",
            f"هماهنگی تحویل «{book_title}» شروع شد",
            "زمان و محل تحویل را با هم هماهنگ کنید.", link,
        )
    elif new_status == "delivered":
        push_notification(
            cur, requester_id, "request_status",
            f"«{book_title}» تحویل داده شد",
            "صاحب کتاب تحویل را ثبت کرد؛ پس از دریافت، در پنل تأیید کن.", link,
        )
    elif new_status == "on_loan":
        push_notification(
            cur, owner_id, "request_status",
            f"«{book_title}» تحویل گرفته شد",
            "امانت شروع شد. موعد بازگشت را در پنل ببین.", link,
        )
    elif new_status == "returned":
        push_notification(
            cur, requester_id, "request_status",
            f"«{book_title}» بازگردانده شد",
            "بازگشت کتاب ثبت شد. می‌توانی امتیاز و نظرت را ثبت کنی.", link,
        )
    elif new_status == "completed":
        push_notification(
            cur, owner_id, "request_status",
            f"خرید «{book_title}» تکمیل شد",
            "خریدار دریافت کتاب را تأیید کرد.", link,
        )


def sync_due_notifications(user_id):
    """برای امانت‌های نزدیک موعد، اعلان یک‌باره می‌سازد (هم برای صاحب و هم امانت‌گیرنده)."""
    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute(
                """SELECT r.id, r.requester_id, r.owner_id, r.due_at, b.title
                   FROM book_requests r JOIN books b ON b.id = r.book_id
                   WHERE r.status = 'on_loan' AND r.reminder_sent = 0
                     AND r.due_at IS NOT NULL
                     AND r.due_at <= DATE_ADD(CURDATE(), INTERVAL %s DAY)
                     AND (r.requester_id = %s OR r.owner_id = %s)""",
                (DUE_SOON_DAYS, user_id, user_id),
            )
            rows = cur.fetchall()
            for row in rows:
                days_left = (row["due_at"] - date.today()).days
                when = "امروز" if days_left == 0 else (
                    f"{abs(days_left)} روز پیش" if days_left < 0 else f"{days_left} روز دیگر"
                )
                body = f"موعد بازگشت «{row['title']}» {when} است."
                push_notification(
                    cur, row["requester_id"], "due_soon",
                    "یادآوری موعد بازگشت کتاب", body, "/panel.html#loans",
                )
                push_notification(
                    cur, row["owner_id"], "due_soon",
                    "یادآوری موعد بازگشت کتاب", body, "/panel.html#loans",
                )
                cur.execute("UPDATE book_requests SET reminder_sent = 1 WHERE id = %s", (row["id"],))
            if rows:
                db.commit()
    except MySQLError:
        app.logger.warning("Due reminder sync failed", exc_info=True)


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
            request_id = cur.lastrowid

            cur.execute("SELECT name FROM users WHERE id=%s", (current_user_id(),))
            requester = cur.fetchone()
            requester_name = (requester or {}).get("name") or "یک کاربر"
            push_notification(
                cur, book["user_id"], "request_new",
                f"درخواست تازه برای «{book['title']}»",
                f"{requester_name} برای این کتاب درخواست فرستاد. تأیید یا رد کن.",
                "/panel.html#requests",
            )
            db.commit()
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
    """وضعیت درخواست را در چرخه‌ی امانت/خرید جلو می‌برد.

    هر گذار مجاز، نقش مجاز و شرط زمانی خودش را دارد (REQUEST_TRANSITIONS)؛
    تاریخ تحویل و موعد بازگشت هم در همین نقطه ثبت می‌شوند.
    """
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401
    if rate_limited(request_bucket("reqstatus", str(current_user_id())), 60, 3600):
        return json_error("تعداد تغییر وضعیت‌ها زیاد است؛ کمی بعد دوباره تلاش کن.", 429)

    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()
    if new_status not in REQUEST_STATUSES:
        return json_error("وضعیت درخواست معتبر نیست.")

    db = get_db()
    try:
        cur = db.cursor(dictionary=True, buffered=True)
        try:
            cur.execute(
                """SELECT r.*, b.title AS book_title, b.duration AS book_duration
                   FROM book_requests r JOIN books b ON b.id = r.book_id
                   WHERE r.id=%s""",
                (request_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify(error="درخواست پیدا نشد."), 404

            # اول دسترسی، بعد وضعیت؛ تا کاربر بیگانه از حالت درخواست خبردار نشود.
            role = request_role(row)
            if not role:
                return jsonify(error="به این درخواست دسترسی نداری."), 403

            if new_status not in REQUEST_TRANSITIONS:
                return json_error("این تغییر وضعیت پشتیبانی نمی‌شود.")

            allowed_from, actor = REQUEST_TRANSITIONS[new_status]
            if actor != "both" and actor != role:
                messages = {
                    "owner": "این کار فقط از طرف صاحب کتاب انجام می‌شود.",
                    "requester": "این کار فقط از طرف درخواست‌دهنده انجام می‌شود.",
                }
                return jsonify(error=messages.get(actor, "اجازه‌ی این تغییر را نداری.")), 403
            if row["status"] not in allowed_from:
                return json_error(
                    f"از وضعیت «{REQUEST_STATUS_LABELS.get(row['status'], row['status'])}» "
                    f"نمی‌شود به «{REQUEST_STATUS_LABELS[new_status]}» رفت.", 409,
                )
            if new_status == "on_loan" and row["share_type"] == "sale":
                return json_error("این درخواست خرید است و امانت ندارد.")
            if new_status == "completed" and row["share_type"] != "sale":
                return json_error("این درخواست امانت است و با «بازگشت کتاب» بسته می‌شود.")

            extra_sql = ""
            params = [new_status]

            if new_status == "delivered":
                # تاریخ تحویل همین حالا ثبت و موعد بازگشت از مدت امانت محاسبه می‌شود.
                delivered_at = datetime.now()
                duration_days = row.get("book_duration") or 14
                due_at = (delivered_at + timedelta(days=int(duration_days))).date()
                extra_sql = ", delivered_at=%s, due_at=%s, reminder_sent=0"
                params.extend([delivered_at, due_at])
            elif new_status == "returned":
                extra_sql = ", returned_at=%s"
                params.append(datetime.now())
            elif new_status == "completed":
                extra_sql = ", completed_at=%s"
                params.append(datetime.now())

            params.append(request_id)
            cur.execute(f"UPDATE book_requests SET status=%s{extra_sql} WHERE id=%s", params)

            # با تأیید یک درخواست، بقیه‌ی درخواست‌های همان کتاب خودکار رد می‌شوند.
            if new_status == "accepted":
                cur.execute(
                    """SELECT id, requester_id FROM book_requests
                       WHERE book_id=%s AND status='pending' AND id<>%s""",
                    (row["book_id"], request_id),
                )
                others = cur.fetchall()
                if others:
                    cur.execute(
                        """UPDATE book_requests SET status='rejected'
                           WHERE book_id=%s AND status='pending' AND id<>%s""",
                        (row["book_id"], request_id),
                    )
                    for other in others:
                        push_notification(
                            cur, other["requester_id"], "request_status",
                            f"درخواست «{row['book_title']}» بسته شد",
                            "کتاب به درخواست‌دهنده‌ی دیگری تحویل داده می‌شود.", "/panel.html#requests",
                        )

            notify_status_change(cur, row, new_status, row["book_title"])
            db.commit()
        finally:
            cur.close()
    except MySQLError:
        app.logger.exception("Request status update failed")
        return json_error("تغییر وضعیت درخواست انجام نشد.", 503)
    finally:
        db.close()

    return jsonify(success=True, id=request_id, status=new_status, statusLabel=REQUEST_STATUS_LABELS[new_status])


@app.route("/api/loans", methods=["GET"])
def list_loans():
    """امانت‌ها و خریدهای در جریان و تاریخچه‌ی کامل، برای تب «پیگیری امانت»."""
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401

    user_id = current_user_id()
    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute(
                """SELECT r.*, b.title AS book_title,
                          requester.name AS requester_name,
                          owner.name AS owner_name
                   FROM book_requests r
                   JOIN books b ON b.id = r.book_id
                   JOIN users requester ON requester.id = r.requester_id
                   JOIN users owner ON owner.id = r.owner_id
                   WHERE (r.requester_id=%s OR r.owner_id=%s)
                     AND r.status NOT IN ('pending', 'rejected', 'cancelled')
                   ORDER BY COALESCE(r.due_at, r.updated_at) ASC
                   LIMIT 100""",
                (user_id, user_id),
            )
            rows = cur.fetchall()
    except MySQLError:
        app.logger.exception("Loan listing failed")
        return json_error("دریافت امانت‌ها انجام نشد.", 503)

    sync_due_notifications(user_id)

    loans = [request_to_dict(row) for row in rows]
    active = [l for l in loans if l["status"] in {"accepted", "coordinating", "delivered", "on_loan"}]
    history = [l for l in loans if l["status"] in {"returned", "completed"}]
    overdue = [l for l in loans if l["isOverdue"]]

    return jsonify(
        active=active,
        history=history,
        overdueCount=len(overdue),
        dueSoonCount=len([l for l in active if l["daysLeft"] is not None and 0 <= l["daysLeft"] <= DUE_SOON_DAYS]),
    )


# ---------- اعلان‌های داخل سایت ----------
@app.route("/api/notifications", methods=["GET"])
def list_notifications():
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401

    sync_due_notifications(current_user_id())
    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute(
                """SELECT id, type, title, body, link, is_read, created_at
                   FROM notifications WHERE user_id=%s
                   ORDER BY created_at DESC, id DESC LIMIT 30""",
                (current_user_id(),),
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT COUNT(*) AS total FROM notifications WHERE user_id=%s AND is_read=0",
                (current_user_id(),),
            )
            unread = int((cur.fetchone() or {}).get("total") or 0)
    except MySQLError:
        app.logger.exception("Notification listing failed")
        return json_error("دریافت اعلان‌ها انجام نشد.", 503)

    items = [{
        "id": row["id"],
        "type": row["type"],
        "title": row["title"],
        "body": row["body"],
        "link": row["link"],
        "isRead": bool(row["is_read"]),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
    } for row in rows]

    return jsonify(items=items, unread=unread)


@app.route("/api/notifications/read", methods=["POST"])
def mark_notifications_read():
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401

    data = request.get_json(silent=True) or {}
    notification_id = data.get("id")
    try:
        with db_cursor() as (db, cur):
            if notification_id:
                cur.execute(
                    "UPDATE notifications SET is_read=1 WHERE id=%s AND user_id=%s",
                    (notification_id, current_user_id()),
                )
            else:
                cur.execute(
                    "UPDATE notifications SET is_read=1 WHERE user_id=%s AND is_read=0",
                    (current_user_id(),),
                )
            db.commit()
    except MySQLError:
        app.logger.exception("Marking notifications read failed")
        return json_error("ثبت خوانده‌شدن اعلان‌ها انجام نشد.", 503)

    return jsonify(success=True)


# ---------- علاقه‌مندی‌ها ----------
@app.route("/api/books/<int:book_id>/favorite", methods=["GET", "POST"])
def toggle_favorite(book_id):
    """GET وضعیت فعلی را می‌دهد؛ POST آن را روشن/خاموش می‌کند (دکمه‌ی قلب)."""
    if not current_user_id():
        if request.method == "GET":
            return jsonify(favorited=False, loggedIn=False)
        return jsonify(error="برای ذخیره‌ی کتاب باید وارد حساب شوی."), 401

    if request.method == "GET":
        try:
            with db_cursor(dictionary=True) as (_db, cur):
                cur.execute(
                    "SELECT id FROM favorites WHERE user_id=%s AND book_id=%s",
                    (current_user_id(), book_id),
                )
                favorited = bool(cur.fetchone())
        except MySQLError:
            app.logger.exception("Favorite state read failed")
            return json_error("وضعیت علاقه‌مندی خوانده نشد.", 503)
        return jsonify(favorited=favorited, loggedIn=True)

    if rate_limited(request_bucket("fav", str(current_user_id())), 120, 3600):
        return json_error("تعداد تغییرها زیاد است؛ کمی بعد دوباره تلاش کن.", 429)

    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute("SELECT id FROM books WHERE id=%s", (book_id,))
            if not cur.fetchone():
                return jsonify(error="کتاب پیدا نشد."), 404

            cur.execute(
                "SELECT id FROM favorites WHERE user_id=%s AND book_id=%s",
                (current_user_id(), book_id),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute("DELETE FROM favorites WHERE id=%s", (existing["id"],))
                favorited = False
            else:
                cur.execute(
                    "INSERT INTO favorites (user_id, book_id) VALUES (%s, %s)",
                    (current_user_id(), book_id),
                )
                favorited = True
            db.commit()
    except MySQLError:
        app.logger.exception("Favorite toggle failed")
        return json_error("ذخیره‌ی علاقه‌مندی انجام نشد.", 503)

    return jsonify(success=True, favorited=favorited)


@app.route("/api/favorites", methods=["GET"])
def list_favorites():
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401

    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute(
                f"""SELECT books.*, users.name AS owner_name, {BOOK_ENRICH_COLUMNS}
                    FROM favorites f
                    JOIN books ON books.id = f.book_id
                    JOIN users ON users.id = books.user_id
                    WHERE f.user_id=%s
                    ORDER BY f.created_at DESC""",
                (current_user_id(), current_user_id()),
            )
            rows = cur.fetchall()
    except MySQLError:
        app.logger.exception("Favorite listing failed")
        return json_error("دریافت علاقه‌مندی‌ها انجام نشد.", 503)

    return jsonify([book_to_dict(row) for row in rows])


# ---------- امتیاز و نظر ----------
def review_eligibility(cur, book_id, user_id):
    """آیا کاربر این کتاب را واقعاً امانت گرفته یا خریده و کارش تمام شده است؟"""
    cur.execute(
        """SELECT id FROM book_requests
           WHERE book_id=%s AND requester_id=%s AND status IN ('returned', 'completed')
           ORDER BY updated_at DESC LIMIT 1""",
        (book_id, user_id),
    )
    row = cur.fetchone()
    return row["id"] if row else None


@app.route("/api/books/<int:book_id>/reviews", methods=["GET"])
def list_reviews(book_id):
    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute("SELECT id FROM books WHERE id=%s", (book_id,))
            if not cur.fetchone():
                return jsonify(error="کتاب پیدا نشد."), 404

            cur.execute(
                """SELECT rv.id, rv.rating, rv.comment, rv.created_at, rv.user_id,
                          u.name AS user_name
                   FROM reviews rv JOIN users u ON u.id = rv.user_id
                   WHERE rv.book_id=%s
                   ORDER BY rv.created_at DESC LIMIT 50""",
                (book_id,),
            )
            rows = cur.fetchall()

            my_review = None
            can_review = False
            if current_user_id():
                cur.execute(
                    "SELECT id, rating, comment FROM reviews WHERE book_id=%s AND user_id=%s",
                    (book_id, current_user_id()),
                )
                mine = cur.fetchone()
                if mine:
                    my_review = {"id": mine["id"], "rating": mine["rating"], "comment": mine["comment"]}
                # داشتن نظر قبلی هم اجازه‌ی ویرایش می‌دهد، حتی اگر وضعیت درخواست عوض شده باشد.
                can_review = bool(my_review) or bool(review_eligibility(cur, book_id, current_user_id()))
    except MySQLError:
        app.logger.exception("Review listing failed")
        return json_error("دریافت نظرها انجام نشد.", 503)

    total = sum(r["rating"] for r in rows)
    items = [{
        "id": r["id"],
        "rating": r["rating"],
        "comment": r["comment"],
        "userName": r["user_name"],
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        "isMine": r["user_id"] == current_user_id(),
    } for r in rows]

    return jsonify(
        reviews=items,
        count=len(rows),
        average=round(total / len(rows), 1) if rows else None,
        canReview=can_review,
        myReview=my_review,
    )


@app.route("/api/books/<int:book_id>/reviews", methods=["POST"])
def save_review(book_id):
    """ثبت یا ویرایش نظر؛ فقط برای کسی که امانت/خرید را کامل کرده است."""
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401
    if rate_limited(request_bucket("review", str(current_user_id())), 20, 3600):
        return json_error("تعداد ثبت نظرها زیاد است؛ کمی بعد دوباره تلاش کن.", 429)

    data = request.get_json(silent=True) or {}
    comment = (data.get("comment") or "").strip()
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        return json_error("امتیاز باید عددی بین ۱ تا ۵ باشد.")
    if not 1 <= rating <= 5:
        return json_error("امتیاز باید بین ۱ تا ۵ باشد.")
    if len(comment) > 700:
        return json_error("متن نظر حداکثر ۷۰۰ نویسه می‌تواند باشد.")

    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute("SELECT user_id, title FROM books WHERE id=%s", (book_id,))
            book = cur.fetchone()
            if not book:
                return jsonify(error="کتاب پیدا نشد."), 404
            if book["user_id"] == current_user_id():
                return json_error("برای کتاب خودت نمی‌توانی نظر بدهی.")

            request_id = review_eligibility(cur, book_id, current_user_id())
            if not request_id:
                # اگر نظر قبلی دارد، ویرایشش مجاز است؛ فقط نظر تازه نیاز به امانت کامل‌شده دارد.
                cur.execute(
                    "SELECT id FROM reviews WHERE book_id=%s AND user_id=%s",
                    (book_id, current_user_id()),
                )
                if not cur.fetchone():
                    return json_error("ثبت امتیاز فقط بعد از کامل‌شدن یک امانت یا خرید همین کتاب ممکن است.", 403)

                cur.execute(
                    "UPDATE reviews SET rating=%s, comment=%s WHERE book_id=%s AND user_id=%s",
                    (rating, comment or None, book_id, current_user_id()),
                )
            else:
                cur.execute(
                    """INSERT INTO reviews (book_id, user_id, request_id, rating, comment)
                       VALUES (%s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE rating=VALUES(rating), comment=VALUES(comment),
                                               request_id=VALUES(request_id)""",
                    (book_id, current_user_id(), request_id, rating, comment or None),
                )
            db.commit()

            cur.execute(
                "SELECT AVG(rating) AS avg_rating, COUNT(*) AS total FROM reviews WHERE book_id=%s",
                (book_id,),
            )
            stats = cur.fetchone() or {}
    except MySQLError:
        app.logger.exception("Review save failed")
        return json_error("ثبت نظر انجام نشد. دوباره تلاش کنید.", 503)

    return jsonify(
        success=True,
        average=round(float(stats.get("avg_rating") or 0), 1),
        count=int(stats.get("total") or 0),
    )


@app.route("/api/books/<int:book_id>/reviews", methods=["DELETE"])
def delete_review(book_id):
    if not current_user_id():
        return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401

    try:
        with db_cursor() as (db, cur):
            cur.execute(
                "DELETE FROM reviews WHERE book_id=%s AND user_id=%s",
                (book_id, current_user_id()),
            )
            db.commit()
    except MySQLError:
        app.logger.exception("Review delete failed")
        return json_error("حذف نظر انجام نشد.", 503)

    return jsonify(success=True)


# ---------- پنل مدیریت ----------
# این‌ها فقط از متغیر محیطی خوانده می‌شوند و هیچ مقدار پیش‌فرضی در کد نیست
# (تا ایمیل/رمز واقعی وارد مخزن گیت نشود). در .env خودت تنظیمشان کن.
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or ""
ADMIN_NAME = os.getenv("ADMIN_NAME") or "مدیر سایت"


def admin_required(view):
    """فقط کاربری که is_admin دارد اجازه‌ی این مسیرها را دارد."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user_id():
            return jsonify(error="ابتدا وارد حساب کاربری‌ات شو."), 401
        try:
            with db_cursor() as (_db, cur):
                cur.execute("SELECT is_admin FROM users WHERE id=%s", (current_user_id(),))
                row = cur.fetchone()
        except MySQLError:
            return json_error("ارتباط با پایگاه‌داده برقرار نشد.", 503)

        if not row:
            session.clear()
            return jsonify(error="این حساب دیگر وجود ندارد."), 401
        if not int(row[0]):
            session["is_admin"] = False
            return jsonify(error="به پنل مدیریت دسترسی نداری."), 403
        return view(*args, **kwargs)
    return wrapper


def ensure_admin_account():
    """حساب مدیر را می‌سازد (اگر نباشد) و همیشه دسترسی مدیریت را روشن می‌کند."""
    if os.getenv("ENSURE_ADMIN", "1") != "1":
        return
    if not ADMIN_EMAIL:
        app.logger.info("ADMIN_EMAIL تنظیم نشده است؛ ساخت خودکار حساب مدیر رد شد.")
        return
    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute("SELECT id, is_admin FROM users WHERE email=%s", (ADMIN_EMAIL,))
            user = cur.fetchone()
            if user:
                if not user["is_admin"]:
                    cur.execute("UPDATE users SET is_admin=1 WHERE id=%s", (user["id"],))
                    db.commit()
                    app.logger.info("Promoted %s to admin", ADMIN_EMAIL)
                return

            if not ADMIN_PASSWORD:
                app.logger.warning(
                    "ADMIN_PASSWORD تنظیم نشده است؛ حساب مدیر %s ساخته نشد.", ADMIN_EMAIL,
                )
                return

            cur.execute(
                "INSERT INTO users (name, email, password_hash, is_admin) VALUES (%s,%s,%s,1)",
                (ADMIN_NAME, ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD)),
            )
            db.commit()
            app.logger.info("Created admin account %s", ADMIN_EMAIL)
    except MySQLError:
        app.logger.warning("Could not ensure admin account", exc_info=True)


def iso(value):
    return value.isoformat() if value else None


@app.route("/api/admin/overview")
@admin_required
def admin_overview():
    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute(
                """SELECT
                     (SELECT COUNT(*) FROM users) AS users,
                     (SELECT COUNT(*) FROM users WHERE last_login_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)) AS active_users,
                     (SELECT COUNT(*) FROM books) AS books,
                     (SELECT COUNT(*) FROM book_requests) AS requests,
                     (SELECT COUNT(*) FROM book_requests WHERE status='pending') AS pending,
                     (SELECT COUNT(*) FROM book_requests WHERE status='on_loan') AS on_loan,
                     (SELECT COUNT(*) FROM reviews) AS reviews,
                     (SELECT COUNT(*) FROM favorites) AS favorites"""
            )
            stats = cur.fetchone() or {}

            cur.execute(
                """SELECT id, name, email, is_admin, created_at, last_login_at, login_count
                   FROM users ORDER BY COALESCE(last_login_at, created_at) DESC LIMIT 6"""
            )
            recent_users = cur.fetchall()

            cur.execute(
                """SELECT b.id, b.title, b.created_at, u.name AS owner_name
                   FROM books b JOIN users u ON u.id = b.user_id
                   ORDER BY b.created_at DESC LIMIT 6"""
            )
            recent_books = cur.fetchall()

            cur.execute(
                """SELECT rv.id, rv.rating, rv.comment, rv.created_at,
                          b.title AS book_title, u.name AS user_name
                   FROM reviews rv
                   JOIN books b ON b.id = rv.book_id
                   JOIN users u ON u.id = rv.user_id
                   ORDER BY rv.created_at DESC LIMIT 6"""
            )
            recent_reviews = cur.fetchall()
    except MySQLError:
        app.logger.exception("Admin overview failed")
        return json_error("دریافت اطلاعات پنل مدیریت انجام نشد.", 503)

    return jsonify(
        stats={key: int(value or 0) for key, value in stats.items()},
        recentUsers=[{
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "isAdmin": bool(row["is_admin"]),
            "createdAt": iso(row["created_at"]),
            "lastLoginAt": iso(row["last_login_at"]),
            "loginCount": int(row["login_count"] or 0),
        } for row in recent_users],
        recentBooks=[{
            "id": row["id"],
            "title": row["title"],
            "ownerName": row["owner_name"],
            "createdAt": iso(row["created_at"]),
        } for row in recent_books],
        recentReviews=[{
            "id": row["id"],
            "rating": row["rating"],
            "comment": row["comment"],
            "bookTitle": row["book_title"],
            "userName": row["user_name"],
            "createdAt": iso(row["created_at"]),
        } for row in recent_reviews],
    )


@app.route("/api/admin/users")
@admin_required
def admin_users():
    q = (request.args.get("q") or "").strip()
    params = []
    where = ""
    if q:
        term = f"%{q}%"
        where = "WHERE (u.name LIKE %s OR u.email LIKE %s OR u.phone LIKE %s)"
        params.extend([term, term, term])

    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute(
                f"""SELECT u.id, u.name, u.email, u.phone, u.is_admin,
                           u.created_at, u.last_login_at, u.login_count,
                           (SELECT COUNT(*) FROM books b WHERE b.user_id = u.id) AS book_count,
                           (SELECT COUNT(*) FROM book_requests r WHERE r.requester_id = u.id) AS request_count,
                           (SELECT COUNT(*) FROM reviews rv WHERE rv.user_id = u.id) AS review_count
                    FROM users u
                    {where}
                    ORDER BY COALESCE(u.last_login_at, u.created_at) DESC
                    LIMIT 200""",
                params,
            )
            rows = cur.fetchall()
    except MySQLError:
        app.logger.exception("Admin users listing failed")
        return json_error("دریافت فهرست کاربران انجام نشد.", 503)

    return jsonify([{
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
        "isAdmin": bool(row["is_admin"]),
        "isMe": row["id"] == current_user_id(),
        "createdAt": iso(row["created_at"]),
        "lastLoginAt": iso(row["last_login_at"]),
        "loginCount": int(row["login_count"] or 0),
        "bookCount": int(row["book_count"] or 0),
        "requestCount": int(row["request_count"] or 0),
        "reviewCount": int(row["review_count"] or 0),
    } for row in rows])


@app.route("/api/admin/users/<int:user_id>", methods=["POST"])
@admin_required
def admin_update_user(user_id):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    make_admin = bool(data.get("isAdmin"))

    if not 2 <= len(name) <= 255:
        return json_error("نام باید بین ۲ تا ۲۵۵ نویسه باشد.")
    if "@" not in email or len(email) > 255:
        return json_error("ایمیل معتبر نیست.")
    if phone and not re.fullmatch(r"09\d{9}", phone):
        return json_error("شماره موبایل باید با ۰۹ شروع شود و ۱۱ رقم باشد.")

    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute("SELECT id, is_admin FROM users WHERE id=%s", (user_id,))
            target = cur.fetchone()
            if not target:
                return jsonify(error="کاربر پیدا نشد."), 404

            cur.execute("SELECT id FROM users WHERE email=%s AND id<>%s", (email, user_id))
            if cur.fetchone():
                return jsonify(error="این ایمیل برای کاربر دیگری ثبت شده است."), 409

            # مدیر نمی‌تواند دسترسی مدیریت خودش را بگیرد (قفل‌شدن پنل).
            if user_id == current_user_id() and not make_admin:
                return json_error("نمی‌توانی دسترسی مدیریت خودت را برداری.")

            if not make_admin and target["is_admin"]:
                cur.execute("SELECT COUNT(*) AS total FROM users WHERE is_admin=1")
                if int((cur.fetchone() or {}).get("total") or 0) <= 1:
                    return json_error("حداقل یک مدیر باید باقی بماند.")

            cur.execute(
                "UPDATE users SET name=%s, email=%s, phone=%s, is_admin=%s WHERE id=%s",
                (name, email, phone or None, 1 if make_admin else 0, user_id),
            )
            db.commit()
    except MySQLError:
        app.logger.exception("Admin user update failed")
        return json_error("ذخیره‌ی کاربر انجام نشد.", 503)

    if user_id == current_user_id():
        session["user_name"] = name
        session["is_admin"] = make_admin

    return jsonify(success=True)


@app.route("/api/admin/users/<int:user_id>/password", methods=["POST"])
@admin_required
def admin_reset_password(user_id):
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    if len(password) < 8:
        return json_error("رمز جدید باید حداقل ۸ نویسه باشد.")

    try:
        with db_cursor() as (db, cur):
            cur.execute(
                "UPDATE users SET password_hash=%s WHERE id=%s",
                (generate_password_hash(password), user_id),
            )
            if cur.rowcount == 0:
                return jsonify(error="کاربر پیدا نشد."), 404
            db.commit()
    except MySQLError:
        app.logger.exception("Admin password reset failed")
        return json_error("تغییر رمز انجام نشد.", 503)

    return jsonify(success=True)


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def admin_delete_user(user_id):
    if user_id == current_user_id():
        return json_error("حساب خودت را نمی‌توانی حذف کنی.")

    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute("SELECT id, is_admin FROM users WHERE id=%s", (user_id,))
            target = cur.fetchone()
            if not target:
                return jsonify(error="کاربر پیدا نشد."), 404

            if target["is_admin"]:
                cur.execute("SELECT COUNT(*) AS total FROM users WHERE is_admin=1")
                if int((cur.fetchone() or {}).get("total") or 0) <= 1:
                    return json_error("حداقل یک مدیر باید باقی بماند.")

            # فایل جلد و صفحه‌ی کتاب‌های این کاربر هم پاک می‌شوند.
            cur.execute("SELECT id, cover FROM books WHERE user_id=%s", (user_id,))
            books = cur.fetchall()

            cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
            db.commit()
    except MySQLError:
        app.logger.exception("Admin user delete failed")
        return json_error("حذف کاربر انجام نشد.", 503)

    for book in books:
        if book.get("cover"):
            try:
                os.remove(os.path.join(COVERS_DIR, book["cover"]))
            except OSError:
                pass
        delete_book_page(book["id"])

    return jsonify(success=True, deletedBooks=len(books))


@app.route("/api/admin/books")
@admin_required
def admin_books():
    q = (request.args.get("q") or "").strip()
    params = [current_user_id()]
    where = ""
    if q:
        term = f"%{q}%"
        where = "WHERE (b.title LIKE %s OR b.author LIKE %s OR u.name LIKE %s)"
        params.extend([term, term, term])

    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute(
                f"""SELECT b.*, u.name AS owner_name,
                           (SELECT COUNT(*) FROM book_requests r WHERE r.book_id = b.id) AS request_count,
                           (SELECT COUNT(*) FROM reviews rv WHERE rv.book_id = b.id) AS review_count,
                           (SELECT AVG(rating) FROM reviews rv WHERE rv.book_id = b.id) AS rating_avg,
                           EXISTS(SELECT 1 FROM favorites f WHERE f.book_id = b.id AND f.user_id = %s) AS is_favorite
                    FROM books b JOIN users u ON u.id = b.user_id
                    {where}
                    ORDER BY b.created_at DESC
                    LIMIT 300""",
                params,
            )
            rows = cur.fetchall()
    except MySQLError:
        app.logger.exception("Admin books listing failed")
        return json_error("دریافت فهرست کتاب‌ها انجام نشد.", 503)

    return jsonify([{
        "id": row["id"],
        "title": row["title"],
        "author": row["author"],
        "genre": row["genre"],
        "genreLabel": GENRE_LABELS.get(row["genre"], row["genre"]),
        "condition": row["book_condition"],
        "conditionLabel": CONDITION_LABELS.get(row["book_condition"], row["book_condition"]),
        "shareType": row["share_type"],
        "shareTypeLabel": SHARE_TYPE_BADGE_LABELS.get(row["share_type"], row["share_type"]),
        "duration": row["duration"],
        "depositAmount": row["deposit_amount"],
        "salePrice": row["sale_price"],
        "address": row["address"],
        "description": row["description"],
        "cover": f"/covers/{row['cover']}" if row.get("cover") else None,
        "ownerId": row["user_id"],
        "ownerName": row["owner_name"],
        "detailUrl": f"/books/book_{row['id']}.html",
        "createdAt": iso(row["created_at"]),
        "requestCount": int(row["request_count"] or 0),
        "reviewCount": int(row["review_count"] or 0),
        "ratingAvg": round(float(row["rating_avg"]), 1) if row["rating_avg"] is not None else None,
    } for row in rows])


@app.route("/api/admin/books/<int:book_id>", methods=["POST"])
@admin_required
def admin_update_book(book_id):
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()
    genre = (data.get("genre") or "").strip()
    condition = (data.get("condition") or "").strip()
    share_type = (data.get("shareType") or "free").strip()
    address = (data.get("address") or "").strip()
    description = (data.get("description") or "").strip()

    if not title or not author or not genre or not condition or not address:
        return json_error("عنوان، نویسنده، ژانر، وضعیت و آدرس اجباری‌اند.")
    if share_type not in SHARE_TYPES:
        share_type = "free"

    try:
        duration = parse_amount(data.get("duration"), "مدت امانت")
        deposit_amount = parse_amount(data.get("depositAmount"), "ودیعه")
        sale_price = parse_amount(data.get("salePrice"), "قیمت")
    except ValueError as exc:
        return json_error(str(exc))

    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute("SELECT id FROM books WHERE id=%s", (book_id,))
            if not cur.fetchone():
                return jsonify(error="کتاب پیدا نشد."), 404

            cur.execute(
                """UPDATE books SET title=%s, author=%s, genre=%s, book_condition=%s,
                          share_type=%s, duration=%s, deposit_amount=%s, sale_price=%s,
                          address=%s, description=%s
                   WHERE id=%s""",
                (title, author, genre, condition, share_type, duration or None,
                 deposit_amount or None, sale_price or None, address, description, book_id),
            )
            db.commit()
    except MySQLError:
        app.logger.exception("Admin book update failed")
        return json_error("ذخیره‌ی کتاب انجام نشد.", 503)

    # صفحه‌ی اختصاصی کتاب با اطلاعات تازه از نو ساخته می‌شود.
    rebuild_book_page(book_id)
    return jsonify(success=True, detailUrl=f"/books/book_{book_id}.html")


@app.route("/api/admin/reviews")
@admin_required
def admin_reviews():
    q = (request.args.get("q") or "").strip()
    where = ""
    params = []
    if q:
        term = f"%{q}%"
        where = "WHERE (rv.comment LIKE %s OR b.title LIKE %s OR u.name LIKE %s)"
        params.extend([term, term, term])

    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute(
                f"""SELECT rv.id, rv.rating, rv.comment, rv.created_at,
                           b.id AS book_id, b.title AS book_title,
                           u.id AS user_id, u.name AS user_name, u.email AS user_email
                    FROM reviews rv
                    JOIN books b ON b.id = rv.book_id
                    JOIN users u ON u.id = rv.user_id
                    {where}
                    ORDER BY rv.created_at DESC
                    LIMIT 300""",
                params,
            )
            rows = cur.fetchall()
    except MySQLError:
        app.logger.exception("Admin reviews listing failed")
        return json_error("دریافت نظرات انجام نشد.", 503)

    return jsonify([{
        "id": row["id"],
        "rating": row["rating"],
        "comment": row["comment"],
        "createdAt": iso(row["created_at"]),
        "bookId": row["book_id"],
        "bookTitle": row["book_title"],
        "userId": row["user_id"],
        "userName": row["user_name"],
        "userEmail": row["user_email"],
    } for row in rows])


@app.route("/api/admin/reviews/<int:review_id>", methods=["DELETE"])
@admin_required
def admin_delete_review(review_id):
    try:
        with db_cursor() as (db, cur):
            cur.execute("DELETE FROM reviews WHERE id=%s", (review_id,))
            db.commit()
    except MySQLError:
        app.logger.exception("Admin review delete failed")
        return json_error("حذف نظر انجام نشد.", 503)
    return jsonify(success=True)


@app.route("/api/admin/requests")
@admin_required
def admin_requests():
    status = (request.args.get("status") or "").strip()
    where = ""
    params = []
    if status in REQUEST_STATUSES:
        where = "WHERE r.status=%s"
        params.append(status)

    try:
        with db_cursor(dictionary=True) as (_db, cur):
            cur.execute(
                f"""SELECT r.id, r.status, r.share_type, r.created_at, r.due_at, r.delivered_at,
                           b.title AS book_title, b.id AS book_id,
                           rq.name AS requester_name, ow.name AS owner_name
                    FROM book_requests r
                    JOIN books b ON b.id = r.book_id
                    JOIN users rq ON rq.id = r.requester_id
                    JOIN users ow ON ow.id = r.owner_id
                    {where}
                    ORDER BY r.created_at DESC
                    LIMIT 300""",
                params,
            )
            rows = cur.fetchall()
    except MySQLError:
        app.logger.exception("Admin requests listing failed")
        return json_error("دریافت درخواست‌ها انجام نشد.", 503)

    return jsonify([{
        "id": row["id"],
        "status": row["status"],
        "statusLabel": REQUEST_STATUS_LABELS.get(row["status"], row["status"]),
        "shareTypeLabel": SHARE_TYPE_BADGE_LABELS.get(row["share_type"], row["share_type"]),
        "bookId": row["book_id"],
        "bookTitle": row["book_title"],
        "requesterName": row["requester_name"],
        "ownerName": row["owner_name"],
        "createdAt": iso(row["created_at"]),
        "deliveredAt": iso(row["delivered_at"]),
        "dueAt": iso(row["due_at"]),
    } for row in rows])


@app.route("/api/admin/requests/<int:request_id>", methods=["POST"])
@admin_required
def admin_update_request(request_id):
    """مدیر می‌تواند وضعیت هر درخواستی را مستقیم عوض کند (بدون محدودیت چرخه)."""
    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()
    if new_status not in REQUEST_STATUSES:
        return json_error("وضعیت معتبر نیست.")

    try:
        with db_cursor(dictionary=True) as (db, cur):
            cur.execute(
                """SELECT r.*, b.duration AS duration_days
                   FROM book_requests r JOIN books b ON b.id = r.book_id
                   WHERE r.id=%s""",
                (request_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify(error="درخواست پیدا نشد."), 404

            extra = ""
            params = [new_status]
            if new_status == "delivered" and not row["delivered_at"]:
                delivered_at = datetime.now()
                due_at = (delivered_at + timedelta(days=int(row["duration_days"] or 14))).date()
                extra = ", delivered_at=%s, due_at=%s, reminder_sent=0"
                params.extend([delivered_at, due_at])
            elif new_status == "returned" and not row.get("returned_at"):
                extra = ", returned_at=%s"
                params.append(datetime.now())
            elif new_status == "completed" and not row.get("completed_at"):
                extra = ", completed_at=%s"
                params.append(datetime.now())

            params.append(request_id)
            cur.execute(f"UPDATE book_requests SET status=%s{extra} WHERE id=%s", params)
            db.commit()
    except MySQLError:
        app.logger.exception("Admin request update failed")
        return json_error("تغییر وضعیت انجام نشد.", 503)

    return jsonify(success=True, statusLabel=REQUEST_STATUS_LABELS[new_status])


@app.route("/api/admin/requests/<int:request_id>", methods=["DELETE"])
@admin_required
def admin_delete_request(request_id):
    try:
        with db_cursor() as (db, cur):
            cur.execute("DELETE FROM book_requests WHERE id=%s", (request_id,))
            db.commit()
    except MySQLError:
        app.logger.exception("Admin request delete failed")
        return json_error("حذف درخواست انجام نشد.", 503)
    return jsonify(success=True)


# جدول درخواست‌ها در اولین اجرا (یا نصب‌های قدیمی) ساخته می‌شود.
ensure_schema()
# کتاب‌های نمونه یک‌بار به دیتابیس اضافه می‌شوند تا صفحه‌شان واقعی باشد.
seed_demo_books()
# حساب مدیر (پنل مدیریت) تضمین می‌شود.
ensure_admin_account()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)