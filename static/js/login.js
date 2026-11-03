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

        /* ---------- ورود واقعی (ایمیل + رمز عبور) از طریق بک‌اند Flask ---------- */
        const loginEmailInput = document.getElementById('login-email');
        const loginPasswordInput = document.getElementById('login-password');

        const stepEmail = document.getElementById('login-step-email');
        const loginSuccess = document.getElementById('login-success');
        const authSwitchText = document.getElementById('auth-switch-text');
        const dashboardGreeting = document.getElementById('dashboard-greeting');
        const myBooksList = document.getElementById('my-books-list');
        const myBooksEmpty = document.getElementById('my-books-empty');

        function isValidEmail(value) {
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
        }

        const shareTypeLabels = { free: 'امانت رایگان', deposit: 'امانت با ودیعه', sale: 'فروش' };

        async function loadMyBooks() {
            myBooksList.innerHTML = '';
            try {
                const res = await fetch('/api/my-books');
                if (!res.ok) return;
                const books = await res.json();

                myBooksEmpty.style.display = books.length ? 'none' : 'block';

                books.forEach(book => {
                    const row = document.createElement('div');
                    row.style.cssText = 'display:flex; align-items:center; justify-content:space-between; gap:10px; border:1px solid var(--line); border-radius:10px; padding:10px 14px; margin-bottom:8px;';
                    row.innerHTML = `
                        <div>
                            <strong>${book.title}</strong>
                            <div style="color:var(--ink-soft); font-size:13px;">${book.author} — ${shareTypeLabels[book.shareType] || book.shareType}</div>
                        </div>
                    `;
                    const deleteBtn = document.createElement('button');
                    deleteBtn.type = 'button';
                    deleteBtn.textContent = 'حذف';
                    deleteBtn.style.cssText = 'background:var(--pomegranate); color:#fff; border:none; border-radius:8px; padding:6px 14px; font-family:inherit; cursor:pointer; flex:none;';
                    deleteBtn.addEventListener('click', async () => {
                        if (!confirm(`کتاب «${book.title}» حذف بشه؟`)) return;
                        const res = await fetch(`/api/books/${book.id}`, { method: 'DELETE' });
                        const data = await res.json();
                        if (!res.ok) {
                            alert(data.error || 'حذف انجام نشد.');
                            return;
                        }
                        row.remove();
                        loadMyBooks();
                    });
                    row.appendChild(deleteBtn);
                    myBooksList.appendChild(row);
                });
            } catch (err) {
                /* بک‌اند در دسترس نیست */
            }
        }

        function showDashboard(name) {
            stepEmail.classList.add('step-hidden');
            loginSuccess.classList.add('visible');
            authSwitchText.style.display = 'none';
            dashboardGreeting.textContent = `خوش اومدی، ${name}!`;
            loadMyBooks();
        }

        /* اگر کاربر واردشده، دکمه‌ی «ورود» بالای صفحه رو به اسم خودش تغییر بده */
        fetch('/api/me').then(r => r.json()).then(me => {
            if (me.loggedIn) {
                const loginBtn = document.querySelector('.nav-actions .btn-login');
                if (loginBtn) loginBtn.textContent = me.name;
                showDashboard(me.name);
            }
        });

        document.getElementById('login-submit-btn').addEventListener('click', async () => {
            const email = loginEmailInput.value.trim();
            const password = loginPasswordInput.value;
            const emailField = document.getElementById('field-login-email');
            const passwordField = document.getElementById('field-login-password');

            const emailValid = isValidEmail(email);
            emailField.classList.toggle('error', !emailValid);
            if (!emailValid) return;
            emailField.classList.remove('error');

            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password }),
                });
                const data = await res.json();

                if (!res.ok) {
                    passwordField.classList.add('error');
                    return;
                }
                passwordField.classList.remove('error');
                showDashboard(data.name);
            } catch (err) {
                alert('اتصال به سرور برقرار نشد. مطمئن شو Flask در حال اجراست.');
            }
        });

        document.getElementById('logout-btn').addEventListener('click', async () => {
            await fetch('/api/logout', { method: 'POST' });
            window.location.reload();
        });
