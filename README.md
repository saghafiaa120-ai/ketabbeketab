<div align="center">

# 📚 کتاب‌به‌کتاب

**پلتفرمی برای امانت، فروش و اشتراک‌گذاری کتاب بین کتاب‌دوست‌ها**

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/Database-MySQL%20%2F%20MariaDB-4479A1?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![RTL](https://img.shields.io/badge/UI-Persian%20%2F%20RTL-1B6062)](#)

</div>

---

## درباره‌ی پروژه

**کتاب‌به‌کتاب** یک وب‌سایت فارسی و راست‌به‌چپ است که قفسه‌ی خانه‌ها را به یک کتابخانه‌ی زنده تبدیل می‌کند.
کاربر ثبت‌نام می‌کند، کتاب‌هایش را با جلد و مشخصات بارگذاری می‌کند و دیگران می‌توانند آن‌ها را
**رایگان امانت بگیرند**، **با ودیعه امانت بگیرند** یا **بخرند**.

بک‌اند با **Flask + MySQL** نوشته شده و فرانت‌اند بدون هیچ فریم‌ورکی (HTML/CSS/JS خالص) در قالب‌های Jinja سرو می‌شود.

> **ورود و ثبت‌نام ساده است:** کاربر جدید ثبت‌نام می‌کند و حسابش همان لحظه فعال می‌شود؛
> کاربری که از قبل حساب دارد با **ایمیل و رمز عبور** وارد می‌شود.
> **هیچ ایمیل تأییدی ارسال نمی‌شود** و پروژه به SMTP یا سرویس ایمیل وابسته نیست.

---

## ✨ امکانات

### حساب کاربری
- ثبت‌نام تک‌مرحله‌ای (نام، ایمیل، موبایل، رمز عبور) و ورود بلافاصله پس از ثبت‌نام
- ورود کاربران قدیمی با ایمیل + رمز عبور
- هش کردن رمز عبور با `Werkzeug` و نشست امن کوکی (`HttpOnly` + `SameSite=Lax`)
- پنل شخصی بعد از ورود: فهرست کتاب‌های خودِ کاربر و امکان حذف آن‌ها
- نمایش نام کاربر در نوار بالای همه‌ی صفحات پس از ورود
- **بدون تأیید ایمیل، بدون کد یک‌بارمصرف و بدون SMTP**

### کتاب‌ها
- بارگذاری کتاب همراه با عکس جلد (PNG / JPG / JPEG / WEBP / GIF تا ۵ مگابایت)
- سه نوع اشتراک‌گذاری: امانت رایگان، امانت با ودیعه، فروش
- فهرست عمومی کتاب‌ها با جست‌وجو روی عنوان، نویسنده و ژانر
- **ساخت خودکار صفحه‌ی اختصاصی هر کتاب** از روی قالب `templates/_template.html`
  (`templates/books/book_<id>.html`) و حذف خودکار آن هنگام حذف کتاب
- کتاب‌های نمونه‌ی ثابت در کنار کتاب‌های واقعی نمایش داده می‌شوند

### امنیت و پایداری
- اعتبارسنجی سمت سرور برای همه‌ی ورودی‌ها (طول، نوع، مبلغ صحیح مثبت)
- محدودیت تعداد تلاش برای ثبت‌نام، ورود و آپلود (rate limit سبک در حافظه)
- بررسی محتوای واقعی تصویر جلد با `Pillow` (نه فقط پسوند فایل)
- هدرهای امنیتی پایه: `X-Content-Type-Options`، `X-Frame-Options`، `Referrer-Policy`
- مدیریت اتصال دیتابیس با connection pool و `context manager`
- پاک‌سازی فایل‌های نیمه‌کاره در صورت خطا (جلد و صفحه‌ی کتاب)
- مسیر `GET /api/health` برای پایش وضعیت برنامه و دیتابیس

---

## 🧱 ساختار پروژه

```text
ketabBeketab/
├── app.py                  # برنامه‌ی Flask: API‌ها، احراز هویت، کتاب‌ها
├── wsgi.py                 # نقطه‌ی ورود Gunicorn
├── Procfile                # دستور اجرا در هاست
├── schema.sql              # ساختار دیتابیس MySQL
├── requirements.txt        # وابستگی‌های پایتون
├── .env.example            # نمونه‌ی متغیرهای محیطی
├── templates/              # صفحات HTML (Jinja)
│   ├── index.html          # خانه
│   ├── books.html          # فهرست کتاب‌ها
│   ├── upload.html         # بارگذاری کتاب
│   ├── login.html          # ورود / پنل کاربر
│   ├── register.html       # ثبت‌نام
│   ├── process.html        # روند امانت
│   ├── community.html      # باشگاه خوانندگان
│   ├── about.html          # درباره‌ی ما
│   ├── contact.html        # ارتباط با ما
│   ├── _template.html      # قالب ساخت صفحه‌ی هر کتاب
│   └── books/              # کتاب‌های نمونه + صفحات ساخته‌شده
├── static/
│   ├── css/                # استایل هر صفحه
│   ├── js/                 # منطق سمت کاربر
│   ├── fonts/              # فونت محلی Vazirmatn
│   └── images/             # لوگو و تصاویر
├── covers/                 # جلدهای آپلودشده‌ی کاربران
├── راه‌اندازی.md            # راهنمای راه‌اندازی محلی
└── تغییرات-پروژه.md        # گزارش تغییرات فنی پروژه
```

---

## 🚀 راه‌اندازی محلی

### پیش‌نیازها
- Python 3.9 یا بالاتر
- MySQL (یا XAMPP / MariaDB)

### ۱) دیتابیس
اگر XAMPP داری، فقط سرویس **MySQL** را Start کن (به Apache نیازی نیست) و سپس:

```bash
mysql -u root -p < schema.sql
```

یا محتوای `schema.sql` را در تب SQL پایگاه‌داده اجرا کن.

### ۲) محیط مجازی و وابستگی‌ها

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### ۳) متغیرهای محیطی
پروژه تنظیمات را از **متغیرهای محیطی** می‌خواند. فایل `.env.example` فقط فهرست کامل این متغیرها است؛
مقادیر را در شل (یا در پنل متغیرهای هاست) تنظیم کن:

```bash
# Linux / macOS
export DB_USER=root DB_PASSWORD= SECRET_KEY="یک-کلید-تصادفی-طولانی"

# Windows (PowerShell)
$env:DB_USER="root"; $env:DB_PASSWORD=""; $env:SECRET_KEY="یک-کلید-تصادفی-طولانی"
```

اگر از XAMPP با تنظیمات پیش‌فرض استفاده می‌کنی، `DB_USER=root` و `DB_PASSWORD` خالی است.
(چون برنامه با `python app.py` اجرا می‌شود، فایل `.env` خودکار خوانده نمی‌شود.)

### ۴) اجرا

```bash
python app.py
```

سایت روی <http://127.0.0.1:5000> بالا می‌آید. **همیشه از طریق همین آدرس باز کن**؛
باز کردن مستقیم فایل‌های HTML باعث می‌شود درخواست‌های API کار نکنند.

---

## ⚙️ متغیرهای محیطی

| متغیر | پیش‌فرض | توضیح |
| --- | --- | --- |
| `SECRET_KEY` | کلید تصادفی موقت | کلید امضای نشست؛ در production مقدار ثابت و طولانی بگذار |
| `DB_HOST` | `127.0.0.1` | آدرس سرور MySQL |
| `DB_USER` | `root` | کاربر دیتابیس |
| `DB_PASSWORD` | خالی | رمز دیتابیس |
| `DB_NAME` | `ketabbeketab` | نام دیتابیس |
| `COOKIE_SECURE` | `0` | `1` برای کوکی `Secure` روی HTTPS |
| `PORT` | `5000` | پورت اجرای برنامه |
| `FLASK_DEBUG` | `0` | `1` برای حالت توسعه |
| `MAX_UPLOADS_PER_HOUR` | `20` | سقف آپلود کتاب در ساعت برای هر کاربر |

> هیچ متغیر SMTP یا ایمیل لازم نیست؛ ارسال ایمیل از پروژه حذف شده است.

---

## 🔌 API

| متد | مسیر | دسترسی | کار |
| --- | --- | --- | --- |
| `GET` | `/api/health` | عمومی | وضعیت برنامه و اتصال دیتابیس |
| `POST` | `/api/register` | عمومی | ساخت حساب و ورود بلافاصله |
| `POST` | `/api/login` | عمومی | ورود با ایمیل + رمز عبور |
| `POST` | `/api/logout` | کاربر | خروج و پاک‌سازی نشست |
| `GET` | `/api/me` | عمومی | کاربر فعلی (یا `loggedIn: false`) |
| `GET` | `/api/books` | عمومی | فهرست کتاب‌ها با `q`، `page`، `per_page` |
| `GET` | `/api/my-books` | کاربر | کتاب‌های خودِ کاربر |
| `POST` | `/api/books` | کاربر | ثبت کتاب جدید (multipart + جلد) |
| `DELETE` | `/api/books/<id>` | مالک / مدیر | حذف کتاب و صفحه و جلد آن |

نمونه‌ی ثبت‌نام:

```bash
curl -X POST http://127.0.0.1:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"name":"سارا احمدی","email":"sara@example.com","phone":"09123456789","password":"Secret123"}'
```

نمونه‌ی ورود:

```bash
curl -X POST http://127.0.0.1:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sara@example.com","password":"Secret123"}'
```

---

## 🔐 جریان احراز هویت

```text
ثبت‌نام ──▶ اعتبارسنجی ورودی ──▶ ساخت رکورد کاربر (رمز هش‌شده) ──▶ ورود خودکار
                                                                  │
کاربر قدیمی ──▶ ایمیل + رمز عبور ──▶ بررسی هش ──▶ ساخت نشست ◀─────┘
```

- ثبت‌نام و ورود هر دو نشست امن می‌سازند؛ کاربر بدون مرحله‌ی اضافه وارد پنل می‌شود.
- اگر نصب قدیمی جدول `email_verifications` را دارد، می‌توانی بی‌خطر حذفش کنی:

```sql
DROP TABLE IF EXISTS email_verifications;
```

---

## ☁️ اجرا روی هاست

`Procfile` برای Gunicorn آماده است:

```text
web: gunicorn --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT wsgi:app
```

در هاست، متغیرهای محیطی را تنظیم کن و مطمئن شو پوشه‌های `covers/` و `templates/books/`
دسترسی نوشتن دارند (صفحات کتاب و جلدها روی دیسک ذخیره می‌شوند).

---

## 🗺️ نقشه‌ی راه

- [ ] درخواست واقعی امانت/خرید و پیگیری وضعیت تحویل
- [ ] گفت‌وگوی درون‌برنامه‌ای بین امانت‌دهنده و امانت‌گیرنده
- [ ] بازیابی رمز عبور (بدون وابستگی به ایمیل، مثلاً با موبایل)
- [ ] پنل مدیریت (فیلد `is_admin` از قبل در دیتابیس آماده است)
- [ ] انتقال جلدها و صفحات تولیدشده به فضای ابری یا object storage
- [ ] تست‌های خودکار برای API‌ها

---

## 🤝 مشارکت

1. پروژه را Fork کن
2. یک شاخه بساز: `git checkout -b feature/my-change`
3. تغییراتت را کامیت کن: `git commit -m "Add my change"`
4. شاخه را پوش کن: `git push origin feature/my-change`
5. Pull Request باز کن

برای تغییرات بزرگ‌تر، لطفاً اول یک Issue باز کن تا درباره‌ی رویکرد هم‌فکر شویم.

---

<div align="center">

### English summary

**Ketab-be-Ketab** is a Persian (RTL) book-sharing platform built with **Flask + MySQL** and vanilla HTML/CSS/JS.
Users sign up (account is active immediately) or log in with **email + password** — there is **no email
verification and no SMTP dependency**. Users upload books with covers, choose free / deposit / sale lending,
and the app generates a dedicated page per book. Includes search, per-user dashboard, rate limiting,
secure sessions and image validation.

</div>
