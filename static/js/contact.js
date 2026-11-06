/* اگر کاربر واردشده، دکمه‌ی «ورود» بالای صفحه رو به اسم خودش تغییر بده */
        fetch('/api/me').then(r => r.json()).then(me => {
            if (me.loggedIn) {
                const loginBtn = document.querySelector('.nav-actions .btn-login');
                if (loginBtn) {
                    loginBtn.textContent = me.name;
                    loginBtn.href = '/panel.html';
                    if (me.pendingRequests) {
                        const badge = document.createElement('span');
                        badge.textContent = String(me.pendingRequests).replace(/[0-9]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
                        badge.style.cssText = 'display:inline-block;margin-inline-start:6px;min-width:18px;padding:0 5px;border-radius:999px;background:#A73B2E;color:#fff;font-size:11px;line-height:18px;text-align:center;';
                        loginBtn.appendChild(badge);
                    }
                }
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

        /* ---------- Contact Form (فقط اعتبارسنجی و نمایش وضعیت در سمت کاربر) ---------- */
        const contactForm = document.getElementById('contact-form');
        const formSuccess = document.getElementById('form-success');

        function setFieldState(fieldId, isValid) {
            const field = document.getElementById(fieldId);
            field.classList.toggle('error', !isValid);
            field.classList.toggle('success', isValid);
        }

        function isValidEmail(value) {
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
        }

        contactForm?.addEventListener('submit', (event) => {
            event.preventDefault();

            const name = document.getElementById('name').value.trim();
            const email = document.getElementById('email').value.trim();
            const subject = document.getElementById('subject').value.trim();
            const message = document.getElementById('message').value.trim();

            const nameValid = name.length > 1;
            const emailValid = isValidEmail(email);
            const subjectValid = subject.length > 1;
            const messageValid = message.length >= 10;

            setFieldState('field-name', nameValid);
            setFieldState('field-email', emailValid);
            setFieldState('field-subject', subjectValid);
            setFieldState('field-message', messageValid);

            const allValid = nameValid && emailValid && subjectValid && messageValid;

            if (!allValid) {
                formSuccess.classList.remove('visible');
                return;
            }

            // این پلتفرم بک‌اند ندارد؛ اینجا فقط وضعیت موفقیت به‌صورت بصری نمایش داده می‌شود.
            formSuccess.classList.add('visible');
            contactForm.reset();
            ['field-name', 'field-email', 'field-subject', 'field-message'].forEach(id => {
                document.getElementById(id).classList.remove('success', 'error');
            });
        });
