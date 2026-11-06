/* اگر کاربر واردشده، دکمه‌ی «ورود» بالای صفحه رو به اسم خودش تغییر بده،
           و اگه صاحبِ همین کتابه، دکمه‌ی حذف رو نشونش بده */
        fetch('/api/me').then(r => r.json()).then(me => {
            if (me.loggedIn) {
                const loginBtn = document.querySelector('.nav-actions .btn-login');
                if (loginBtn) { loginBtn.textContent = me.name; loginBtn.href = '/panel.html'; }

                /* شناسه‌ها از data-attribute خوانده می‌شوند؛ چون این فایل استاتیک است
                   و پلیس‌هولدرهای قالب داخل HTML جایگزین می‌شوند، نه داخل JS. */
                const delBtn = document.getElementById('owner-delete-btn');
                const ownerId = delBtn ? Number(delBtn.dataset.ownerId) : NaN;
                const bookId = delBtn ? delBtn.dataset.bookId : '';

                if (delBtn && Number.isInteger(ownerId) && ownerId > 0 && ownerId === Number(me.id)) {
                    delBtn.style.display = 'block';
                    delBtn.addEventListener('click', async () => {
                        if (!confirm('مطمئنی می‌خوای این کتاب رو حذف کنی؟')) return;
                        const res = await fetch(`/api/books/${bookId}`, { method: 'DELETE' });
                        const data = await res.json();
                        if (!res.ok) {
                            alert(data.error || 'حذف انجام نشد.');
                            return;
                        }
                        window.location.href = '/books.html';
                    });
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

        /* ---------- دکمه‌ی درخواست (چون این پلتفرم بک‌اند درخواست ندارد، فقط یک شبیه‌سازیِ بصری است) ---------- */
        const requestBtn = document.getElementById('request-btn');
        const requestSuccess = document.getElementById('request-success');

        if (requestBtn && requestSuccess) {
            requestBtn.addEventListener('click', () => {
                requestBtn.disabled = true;
                requestBtn.textContent = 'درخواست ارسال شد ✓';
                requestBtn.classList.add('sent');
                requestSuccess.classList.add('visible');
            });
        }
