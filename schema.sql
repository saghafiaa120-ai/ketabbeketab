-- اسکیمای دیتابیس کتاب‌به‌کتاب
-- اجرا در phpMyAdmin یا خط‌فرمان mysql:  mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS ketabbeketab
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE ketabbeketab;

-- ---------- کاربران ----------
CREATE TABLE IF NOT EXISTS users (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(255) NOT NULL,
    email          VARCHAR(255) NOT NULL UNIQUE,
    phone          VARCHAR(20),
    password_hash  VARCHAR(255) NOT NULL,
    is_admin       TINYINT(1) NOT NULL DEFAULT 0,   -- دسترسی به پنل مدیریت
    last_login_at  DATETIME NULL,                   -- آخرین ورود موفق
    login_count    INT NOT NULL DEFAULT 0,          -- تعداد ورودها
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_users_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- کتاب‌ها ----------
CREATE TABLE IF NOT EXISTS books (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    title           VARCHAR(255) NOT NULL,
    author          VARCHAR(255) NOT NULL,
    genre           VARCHAR(50)  NOT NULL,
    book_condition  VARCHAR(50)  NOT NULL,
    share_type      VARCHAR(20)  NOT NULL DEFAULT 'free',   -- free | deposit | sale
    duration        INT          NULL,
    deposit_amount  INT          NULL,
    sale_price      INT          NULL,
    address         VARCHAR(500) NOT NULL,
    description     TEXT,
    cover           VARCHAR(255),
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_books_user_created (user_id, created_at),
    INDEX idx_books_genre (genre),
    INDEX idx_books_share_type (share_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- درخواست‌های امانت / خرید ----------
-- چرخه‌ی وضعیت امانت:
--   pending → accepted → coordinating → delivered → on_loan → returned
--   (برای فروش: pending → accepted → coordinating → delivered → completed)
--   و در هر مرحله‌ی قبل از تحویل: rejected / cancelled
CREATE TABLE IF NOT EXISTS book_requests (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    book_id         INT NOT NULL,
    requester_id    INT NOT NULL,
    owner_id        INT NOT NULL,
    share_type      VARCHAR(20) NOT NULL DEFAULT 'free',   -- free | deposit | sale
    amount          INT NULL,                              -- ودیعه یا قیمت در لحظه‌ی درخواست
    message         VARCHAR(500) NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    delivered_at    DATETIME NULL,                         -- تاریخ تحویل کتاب
    due_at          DATE NULL,                             -- موعد بازگشت
    returned_at     DATETIME NULL,                         -- تاریخ بازگشت واقعی
    completed_at    DATETIME NULL,                         -- تکمیل خرید
    reminder_sent   TINYINT(1) NOT NULL DEFAULT 0,         -- اعلان «نزدیک‌شدن موعد» ارسال شد؟
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_requests_owner_status (owner_id, status),
    INDEX idx_requests_requester (requester_id, status),
    INDEX idx_requests_due (status, due_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- اعلان‌های داخل سایت ----------
CREATE TABLE IF NOT EXISTS notifications (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    type        VARCHAR(30) NOT NULL,          -- request_new | request_status | due_soon | review ...
    title       VARCHAR(255) NOT NULL,
    body        VARCHAR(500) NULL,
    link        VARCHAR(255) NULL,
    is_read     TINYINT(1) NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notifications_user (user_id, is_read, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- علاقه‌مندی‌ها ----------
CREATE TABLE IF NOT EXISTS favorites (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    book_id     INT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_favorite (user_id, book_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- امتیاز و نظر (فقط پس از امانت/خرید کامل‌شده) ----------
CREATE TABLE IF NOT EXISTS reviews (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    book_id     INT NOT NULL,
    user_id     INT NOT NULL,
    request_id  INT NULL,                      -- درخواستی که با آن حق نظر گرفته شده
    rating      TINYINT NOT NULL,              -- ۱ تا ۵
    comment     VARCHAR(700) NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_review (book_id, user_id),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES book_requests(id) ON DELETE SET NULL,
    INDEX idx_reviews_book (book_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
