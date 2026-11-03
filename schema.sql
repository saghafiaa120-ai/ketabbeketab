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
    is_admin       TINYINT(1) NOT NULL DEFAULT 0,   -- برای بعداً؛ فعلاً استفاده نمی‌شود
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
