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

        /* ---------- دکمه‌ی درخواست (چون این پلتفرم بک‌اند ندارد، فقط یک شبیه‌سازیِ بصری است) ---------- */
        const requestBtn = document.getElementById('request-btn');
        const requestSuccess = document.getElementById('request-success');

        requestBtn.addEventListener('click', () => {
            requestBtn.disabled = true;
            requestBtn.textContent = 'درخواست ارسال شد ✓';
            requestBtn.classList.add('sent');
            requestSuccess.classList.add('visible');
        });