/* =========================================================
   صفحه‌ی اختصاصی کتاب — کتاب‌به‌کتاب
   - نمایش نام کاربر در هدر
   - دکمه‌ی حذف برای صاحب کتاب
   - ثبت واقعی درخواست امانت/خرید
========================================================= */
(function () {
    'use strict';

    const el = (id) => document.getElementById(id);
    let currentUser = null;

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

    /* ---------- کاربر فعلی + دکمه‌ی حذف صاحب کتاب ---------- */
    const delBtn = el('owner-delete-btn');
    const ownerId = delBtn ? Number(delBtn.dataset.ownerId) : NaN;
    const bookId = delBtn ? delBtn.dataset.bookId : '';

    fetch('/api/me')
        .then((response) => response.json())
        .then((me) => {
            currentUser = me;
            if (!me.loggedIn) return;

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

            if (delBtn && Number.isInteger(ownerId) && ownerId > 0 && ownerId === Number(me.id)) {
                delBtn.style.display = 'block';
                delBtn.addEventListener('click', async () => {
                    if (!confirm('مطمئنی می‌خوای این کتاب رو حذف کنی؟')) return;
                    const res = await fetch(`/api/books/${bookId}`, { method: 'DELETE' });
                    const data = await res.json().catch(() => ({}));
                    if (!res.ok) {
                        alert(data.error || 'حذف انجام نشد.');
                        return;
                    }
                    window.location.href = '/books.html';
                });
            }
        })
        .catch(() => { /* سرور در دسترس نیست */ });

    /* ---------- ثبت واقعی درخواست امانت / خرید ---------- */
    const requestBtn = el('request-btn');
    const requestSuccess = el('request-success');
    const requestNote = el('request-note');

    function setNote(text, isError) {
        if (!requestNote) return;
        requestNote.textContent = text;
        requestNote.classList.toggle('error', Boolean(isError));
    }

    if (requestBtn) {
        const targetBookId = requestBtn.dataset.bookId || bookId;
        const idleLabel = requestBtn.textContent;

        requestBtn.addEventListener('click', async () => {
            if (!currentUser || !currentUser.loggedIn) {
                location.href = '/login.html';
                return;
            }

            requestBtn.disabled = true;
            requestBtn.textContent = 'در حال ارسال درخواست…';
            setNote('');

            try {
                const res = await fetch(`/api/books/${targetBookId}/requests`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                });
                const data = await res.json().catch(() => ({}));

                if (res.status === 401) {
                    location.href = '/login.html';
                    return;
                }

                if (!res.ok) {
                    requestBtn.disabled = false;
                    requestBtn.textContent = idleLabel;
                    setNote(data.error || 'ثبت درخواست انجام نشد. دوباره تلاش کن.', true);
                    if (res.status === 409) {
                        requestBtn.textContent = 'قبلاً درخواست داده‌ای';
                        requestBtn.classList.add('sent');
                        requestBtn.disabled = true;
                    }
                    return;
                }

                requestBtn.textContent = 'درخواست ارسال شد ✓';
                requestBtn.classList.add('sent');
                if (requestSuccess) requestSuccess.classList.add('visible');
                setNote('درخواستت در پنل صاحب کتاب ثبت شد؛ پاسخ را از بخش «درخواست‌ها» ببین.');
            } catch (error) {
                requestBtn.disabled = false;
                requestBtn.textContent = idleLabel;
                setNote('اتصال به سرور برقرار نشد. مطمئن شو Flask در حال اجراست.', true);
            }
        });
    }
})();
