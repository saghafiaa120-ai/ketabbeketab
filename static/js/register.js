/* اگر کاربر واردشده، دکمه‌ی «ورود» بالای صفحه رو به اسم خودش تغییر بده */
        fetch('/api/me').then(r => r.json()).then(me => {
            if (me.loggedIn) {
                const loginBtn = document.querySelector('.nav-actions .btn-login');
                if (loginBtn) loginBtn.textContent = me.name;
            }
        });

        /* ---------- Mobile Menu ---------- */
        document.querySelector('.menu-btn')?.addEventListener('click', () => {
            const menuButton = document.querySelector('.menu-btn');
            const navigation = document.querySelector('.nav-links');
            const isOpen = navigation.classList.toggle('open');
            menuButton.setAttribute('aria-expanded', String(isOpen));
        });

        /* ---------- Scroll Reveal ---------- */
        const revealEls = document.querySelectorAll('.reveal');

        if ('IntersectionObserver' in window) {
            const io = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('visible');
                        io.unobserve(entry.target);
                    }
                });
            }, {
                threshold: 0.15,
                rootMargin: '0px 0px -60px 0px'
            });

            revealEls.forEach(el => io.observe(el));
        } else {
            revealEls.forEach(el => el.classList.add('visible'));
        }

        /* ---------- نمایش/مخفی‌کردن رمز عبور ---------- */
        document.querySelectorAll('.password-toggle').forEach(btn => {
            btn.addEventListener('click', () => {
                const input = document.getElementById(btn.dataset.target);
                const isHidden = input.type === 'password';
                input.type = isHidden ? 'text' : 'password';
                btn.textContent = isHidden ? 'مخفی' : 'نمایش';
            });
        });

        /* ---------- سنجش زنده‌ی قدرت رمز عبور ---------- */
        const passwordInput = document.getElementById('reg-password');
        const passwordMeter = document.getElementById('password-meter');
        const strengthLabel = document.getElementById('password-strength-label');

        function getPasswordStrength(value) {
            let score = 0;
            if (value.length >= 8) score++;
            if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score++;
            if (/\d/.test(value)) score++;
            if (/[^A-Za-z0-9]/.test(value)) score++;

            if (value.length === 0) return { level: '', score: 0 };
            if (score <= 1) return { level: 'weak', score };
            if (score <= 2) return { level: 'medium', score };
            return { level: 'strong', score };
        }

        const strengthLabels = {
            weak: 'ضعیف — حروف بزرگ و عدد اضافه کن.',
            medium: 'متوسط — یک نویسه‌ی خاص هم اضافه کن.',
            strong: 'قوی — عالیه!'
        };

        passwordInput.addEventListener('input', () => {
            const { level } = getPasswordStrength(passwordInput.value);
            passwordMeter.className = 'password-meter' + (level ? ' ' + level : '');
            strengthLabel.textContent = level
                ? strengthLabels[level]
                : 'حداقل ۸ نویسه، بهتر است شامل عدد و حرف بزرگ باشد.';
        });

        /* ---------- محدود کردن فیلد شماره موبایل به ارقام ---------- */
        const phoneInput = document.getElementById('reg-phone');
        phoneInput.addEventListener('input', () => {
            phoneInput.value = phoneInput.value.replace(/[^0-9]/g, '').slice(0, 11);
        });

        /* ---------- ثبت‌نام دومرحله‌ای با کدِ نمایشی (چون بک‌اند وجود ندارد) ---------- */
        const nameInput = document.getElementById('reg-name');
        const emailInput = document.getElementById('reg-email');
        const passwordConfirmInput = document.getElementById('reg-password-confirm');
        const termsCheckbox = document.getElementById('reg-terms');
        const registerCodeInput = document.getElementById('register-code');

        const stepDetails = document.getElementById('register-step-details');
        const stepCode = document.getElementById('register-step-code');
        const registerSuccess = document.getElementById('register-success');
        const registerSwitchText = document.getElementById('register-switch-text');

        const emailDisplay = document.getElementById('register-email-display');
        const termsError = document.getElementById('terms-error');
        let registeredEmail = '';

        function isValidEmail(value) {
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
        }

        function isValidPhone(value) {
            return /^09\d{9}$/.test(value);
        }

        function setFieldState(fieldId, isValid) {
            const field = document.getElementById(fieldId);
            field.classList.toggle('error', !isValid);
            field.classList.toggle('success', isValid);
        }

        document.getElementById('register-submit-btn').addEventListener('click', async () => {
            const nameValid = nameInput.value.trim().length > 1;
            const emailValid = isValidEmail(emailInput.value.trim());
            const phoneValid = isValidPhone(phoneInput.value.trim());
            const passwordValid = passwordInput.value.length >= 8;
            const passwordConfirmValid = passwordConfirmInput.value === passwordInput.value && passwordConfirmInput.value.length > 0;
            const termsValid = termsCheckbox.checked;

            setFieldState('field-name', nameValid);
            setFieldState('field-email', emailValid);
            setFieldState('field-phone', phoneValid);
            setFieldState('field-password', passwordValid);
            setFieldState('field-password-confirm', passwordConfirmValid);
            termsError.style.display = termsValid ? 'none' : 'block';

            const allValid = nameValid && emailValid && phoneValid && passwordValid && passwordConfirmValid && termsValid;
            if (!allValid) return;

            const submitBtn = document.getElementById('register-submit-btn');
            submitBtn.disabled = true;

            try {
                const res = await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: nameInput.value.trim(),
                        email: emailInput.value.trim(),
                        phone: phoneInput.value.trim(),
                        password: passwordInput.value,
                    }),
                });
                const data = await res.json();

                if (!res.ok) {
                    setFieldState('field-email', false);
                    document.querySelector('#field-email .error-msg').textContent = data.error || 'خطایی رخ داد.';
                    submitBtn.disabled = false;
                    return;
                }

                registeredEmail = emailInput.value.trim().toLowerCase();
                emailDisplay.textContent = registeredEmail;
                stepDetails.classList.add('step-hidden');
                stepCode.classList.remove('step-hidden');
                registerSwitchText.style.display = 'none';
                if (!data.emailSent) {
                    alert('حساب ساخته شد، اما ارسال ایمیل انجام نشد. تنظیمات SMTP سرور را بررسی کن.');
                }
            } catch (err) {
                alert('اتصال به سرور برقرار نشد. مطمئن شو Flask در حال اجراست.');
                submitBtn.disabled = false;
            }
        });

        document.getElementById('register-verify-btn').addEventListener('click', async () => {
            const code = registerCodeInput.value.trim();
            const valid = /^\d{6}$/.test(code);
            setFieldState('field-register-code', valid);
            if (!valid) return;
            const verifyButton = document.getElementById('register-verify-btn');
            verifyButton.disabled = true;
            try {
                const res = await fetch('/api/verify-email', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: registeredEmail, code })
                });
                const data = await res.json();
                if (!res.ok) {
                    setFieldState('field-register-code', false);
                    document.querySelector('#field-register-code .error-msg').textContent = data.error || 'کد تأیید نادرست است.';
                    verifyButton.disabled = false;
                    return;
                }
                stepCode.classList.add('step-hidden');
                registerSuccess.classList.add('visible');
                setTimeout(() => { window.location.href = 'login.html'; }, 1200);
            } catch (err) {
                alert('ارتباط با سرور برقرار نشد.');
                verifyButton.disabled = false;
            }
        });

        document.getElementById('register-back-btn').addEventListener('click', () => {
            stepCode.classList.add('step-hidden');
            stepDetails.classList.remove('step-hidden');
            registerSwitchText.style.display = '';
        });
