/* =========================================================
   ورود به حساب — کتاب‌به‌کتاب
   بعد از ورود موفق، کاربر به پنل کاربری (/panel.html) می‌رود.
========================================================= */
(function () {
    'use strict';

    const el = (id) => document.getElementById(id);

    /* ---------- منوی موبایل ---------- */
    document.querySelector('.menu-btn')?.addEventListener('click', () => {
        const menuButton = document.querySelector('.menu-btn');
        const navigation = document.querySelector('.nav-links');
        const isOpen = navigation.classList.toggle('open');
        menuButton.setAttribute('aria-expanded', String(isOpen));
    });

    /* ---------- انیمیشن ورود ---------- */
    const revealEls = document.querySelectorAll('.reveal');
    if ('IntersectionObserver' in window) {
        const io = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    io.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15, rootMargin: '0px 0px -60px 0px' });
        revealEls.forEach((node) => io.observe(node));
    } else {
        revealEls.forEach((node) => node.classList.add('visible'));
    }

    /* ---------- اگر از قبل وارد شده، مستقیم به پنل برود ---------- */
    fetch('/api/me')
        .then((response) => response.json())
        .then((me) => {
            if (me.loggedIn) {
                location.replace('panel.html');
            }
        })
        .catch(() => { /* سرور در دسترس نیست؛ فرم ورود باقی می‌ماند */ });

    /* ---------- فرم ورود ---------- */
    const emailInput = el('login-email');
    const passwordInput = el('login-password');
    const emailField = el('field-login-email');
    const passwordField = el('field-login-password');
    const submitBtn = el('login-submit-btn');

    const emailError = emailField.querySelector('.error-msg');
    const passwordError = passwordField.querySelector('.error-msg');
    const emailErrorDefault = emailError.textContent;
    const passwordErrorDefault = passwordError.textContent;

    function isValidEmail(value) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    }

    function resetErrors() {
        emailField.classList.remove('error');
        passwordField.classList.remove('error');
        emailError.textContent = emailErrorDefault;
        passwordError.textContent = passwordErrorDefault;
    }

    async function submitLogin() {
        const email = emailInput.value.trim();
        const password = passwordInput.value;

        resetErrors();

        let invalid = false;
        if (!isValidEmail(email)) {
            emailField.classList.add('error');
            invalid = true;
        }
        if (!password) {
            passwordField.classList.add('error');
            passwordError.textContent = 'رمز عبورت را وارد کن.';
            invalid = true;
        }
        if (invalid) return;

        submitBtn.disabled = true;
        submitBtn.textContent = 'در حال ورود…';

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email, password: password }),
            });
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                passwordField.classList.add('error');
                passwordError.textContent = data.error || 'ایمیل یا رمز عبور اشتباه است.';
                submitBtn.disabled = false;
                submitBtn.textContent = 'ورود';
                return;
            }

            location.replace('panel.html');
        } catch (error) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'ورود';
            passwordField.classList.add('error');
            passwordError.textContent = 'اتصال به سرور برقرار نشد. مطمئن شو Flask در حال اجراست.';
        }
    }

    submitBtn.addEventListener('click', submitLogin);
    [emailInput, passwordInput].forEach((input) => {
        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') submitLogin();
        });
    });
})();
