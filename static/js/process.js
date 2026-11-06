/* اگر کاربر واردشده، دکمه‌ی «ورود» بالای صفحه رو به اسم خودش تغییر بده */
        fetch('/api/me').then(r => r.json()).then(me => {
            if (me.loggedIn) {
                const loginBtn = document.querySelector('.nav-actions .btn-login');
                if (loginBtn) { loginBtn.textContent = me.name; loginBtn.href = '/panel.html'; }
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

        /* ---------- FAQ Accordion (باز/بسته کردن هر سوال) ---------- */
        function ShowAnswer(element) {
            const p = element.querySelector('p');
            const isOpen = element.classList.contains('open');

            if (isOpen) {
                p.style.height = p.scrollHeight + 'px';
                requestAnimationFrame(() => {
                    element.classList.remove('open');
                    p.style.height = '0px';
                });
            } else {
                element.classList.add('open');
                p.style.height = p.scrollHeight + 'px';
                p.addEventListener('transitionend', function handler() {
                    if (element.classList.contains('open')) {
                        p.style.height = 'auto';
                    }
                    p.removeEventListener('transitionend', handler);
                });
            }
        }
