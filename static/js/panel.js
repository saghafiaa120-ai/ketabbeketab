/* =========================================================
   پنل کاربری کتاب‌به‌کتاب
   - گارد ورود، بارگذاری اطلاعات حساب و کتاب‌ها
   - تب‌ها، ویرایش پروفایل، تغییر رمز، خروج
========================================================= */
(function () {
    'use strict';

    const shareTypeLabels = { free: 'امانت رایگان', deposit: 'امانت با ودیعه', sale: 'فروش' };
    const faDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

    const el = (id) => document.getElementById(id);

    function toFa(value) {
        return String(value).replace(/\d/g, (d) => faDigits[Number(d)]);
    }

    /* ---------- درخواست‌های شبکه ---------- */
    async function api(url, options = {}) {
        const response = await fetch(url, {
            headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
            ...options,
        });
        let data = null;
        try {
            data = await response.json();
        } catch (error) {
            data = null;
        }
        return { ok: response.ok, status: response.status, data: data || {} };
    }

    /* ---------- اعلان کوتاه ---------- */
    let toastTimer = null;
    function toast(message, isError = false) {
        const box = el('toast');
        if (!box) return;
        box.textContent = message;
        box.classList.toggle('bad', isError);
        box.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => box.classList.remove('show'), 3200);
    }

    /* ---------- تب‌ها ---------- */
    const tabs = Array.from(document.querySelectorAll('.panel-tab'));
    const navItems = Array.from(document.querySelectorAll('.panel-nav-item'));

    function showTab(name) {
        tabs.forEach((tab) => tab.classList.toggle('active', tab.id === 'tab-' + name));
        navItems.forEach((item) => {
            const active = item.dataset.tab === name;
            item.classList.toggle('active', active);
            item.setAttribute('aria-current', active ? 'page' : 'false');
        });
        if (location.hash !== '#' + name) {
            history.replaceState(null, '', '#' + name);
        }
    }

    navItems.forEach((item) => item.addEventListener('click', () => showTab(item.dataset.tab)));
    document.querySelectorAll('[data-goto]').forEach((btn) => {
        btn.addEventListener('click', () => showTab(btn.dataset.goto));
    });

    const initialTab = (location.hash || '').replace('#', '');
    if (['overview', 'books', 'settings'].includes(initialTab)) {
        showTab(initialTab);
    }

    /* ---------- منوی موبایل و انیمیشن ورود ---------- */
    document.querySelector('.menu-btn')?.addEventListener('click', () => {
        const menuButton = document.querySelector('.menu-btn');
        const navigation = document.querySelector('.nav-links');
        const isOpen = navigation.classList.toggle('open');
        menuButton.setAttribute('aria-expanded', String(isOpen));
    });

    const revealEls = document.querySelectorAll('.reveal');
    if ('IntersectionObserver' in window) {
        const io = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    io.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
        revealEls.forEach((node) => io.observe(node));
    } else {
        revealEls.forEach((node) => node.classList.add('visible'));
    }

    /* ---------- تاریخ امروز ---------- */
    const dateChip = el('panel-date');
    if (dateChip) {
        try {
            const parts = new Intl.DateTimeFormat('fa-IR', {
                weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
            }).formatToParts(new Date()).reduce((acc, part) => {
                acc[part.type] = part.value;
                return acc;
            }, {});
            dateChip.textContent = [parts.weekday, parts.day, parts.month, parts.year]
                .filter(Boolean).join(' ');
        } catch (error) {
            dateChip.textContent = '';
        }
    }

    /* ---------- اطلاعات حساب ---------- */
    let currentUser = null;

    function initialsOf(name) {
        const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return '؟';
        const first = parts[0].charAt(0);
        const second = parts.length > 1 ? parts[1].charAt(0) : '';
        return (first + second).toUpperCase();
    }

    function fillUser(user) {
        currentUser = user;
        const name = user.name || 'کاربر';
        el('user-avatar').textContent = initialsOf(name);
        el('side-name').textContent = name;
        el('side-email').textContent = user.email || '—';

        const navName = el('nav-user-name');
        if (navName) {
            navName.textContent = name;
            navName.href = '/panel.html';
        }

        el('profile-name').value = name;
        el('profile-phone').value = user.phone || '';
        el('profile-email').value = user.email || '';
        document.title = name + ' | پنل کاربری کتاب‌به‌کتاب';
    }

    /* ---------- کتاب‌های من ---------- */
    function bookCard(book) {
        const card = document.createElement('div');
        card.className = 'my-book';

        const cover = document.createElement('div');
        cover.className = 'my-book-cover';
        cover.textContent = (book.title || '?').trim().charAt(0);

        if (book.cover) {
            const img = document.createElement('img');
            img.src = book.cover;
            img.alt = 'جلد ' + book.title;
            img.loading = 'lazy';
            img.addEventListener('error', () => img.remove());
            cover.appendChild(img);
        }

        const badge = document.createElement('span');
        badge.className = 'my-book-badge';
        badge.textContent = shareTypeLabels[book.shareType] || book.shareType;
        cover.appendChild(badge);

        const body = document.createElement('div');
        body.className = 'my-book-body';

        const title = document.createElement('h3');
        title.textContent = book.title;

        const author = document.createElement('p');
        author.textContent = book.author;

        const where = document.createElement('p');
        where.textContent = '📍 ' + (book.address || 'بدون آدرس');

        const actions = document.createElement('div');
        actions.className = 'my-book-actions';

        const detail = document.createElement('a');
        detail.href = book.detailUrl || '/books.html';
        detail.textContent = 'مشاهده';
        actions.appendChild(detail);

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = 'حذف';
        remove.addEventListener('click', () => deleteBook(book, remove, card));
        actions.appendChild(remove);

        body.append(title, author, where, actions);
        card.append(cover, body);
        return card;
    }

    async function deleteBook(book, button, card) {
        if (!window.confirm('کتاب «' + book.title + '» حذف بشه؟ این کار برگشت‌پذیر نیست.')) return;
        button.disabled = true;
        button.textContent = 'در حال حذف…';

        const result = await api('/api/books/' + book.id, { method: 'DELETE' });
        if (!result.ok) {
            button.disabled = false;
            button.textContent = 'حذف';
            toast(result.data.error || 'حذف انجام نشد.', true);
            return;
        }

        card.remove();
        toast('کتاب حذف شد.');
        loadBooks();
    }

    function renderRecent(books) {
        const box = el('recent-books');
        box.textContent = '';

        if (!books.length) {
            const empty = document.createElement('p');
            empty.className = 'panel-empty';
            empty.textContent = 'هنوز کتابی ثبت نکرده‌ای. از دکمه‌ی «کتاب جدید» شروع کن.';
            box.appendChild(empty);
            return;
        }

        books.slice(0, 4).forEach((book) => {
            const row = document.createElement('a');
            row.className = 'mini-item';
            row.href = book.detailUrl || '/books.html';

            const thumb = document.createElement('img');
            thumb.className = 'mini-thumb';
            thumb.alt = '';
            thumb.loading = 'lazy';
            if (book.cover) {
                thumb.src = book.cover;
            }
            thumb.addEventListener('error', () => thumb.remove());

            const info = document.createElement('div');
            info.className = 'mini-info';
            const title = document.createElement('strong');
            title.textContent = book.title;
            const meta = document.createElement('span');
            meta.textContent = book.author;
            info.append(title, meta);

            const badge = document.createElement('span');
            badge.className = 'mini-badge ' + book.shareType;
            badge.textContent = shareTypeLabels[book.shareType] || book.shareType;

            row.append(thumb, info, badge);
            box.appendChild(row);
        });
    }

    function renderStats(books) {
        const count = (type) => books.filter((book) => book.shareType === type).length;
        el('stat-total').textContent = toFa(books.length);
        el('stat-free').textContent = toFa(count('free'));
        el('stat-deposit').textContent = toFa(count('deposit'));
        el('stat-sale').textContent = toFa(count('sale'));
        el('books-badge').textContent = toFa(books.length);
        el('books-meta').textContent = books.length ? toFa(books.length) + ' کتاب ثبت‌شده' : '‌';
    }

    async function loadBooks() {
        const grid = el('my-books-grid');
        const empty = el('my-books-empty');
        const result = await api('/api/my-books');

        if (result.status === 401) {
            location.replace('login.html');
            return;
        }
        if (!result.ok) {
            toast(result.data.error || 'دریافت کتاب‌ها انجام نشد.', true);
            return;
        }

        const books = Array.isArray(result.data) ? result.data : [];
        grid.textContent = '';
        books.forEach((book) => grid.appendChild(bookCard(book)));
        empty.hidden = books.length > 0;

        renderStats(books);
        renderRecent(books);
    }

    /* ---------- تنظیمات: اطلاعات حساب ---------- */
    const profileForm = el('profile-form');
    const profileNote = el('profile-note');

    function setFieldState(fieldId, state) {
        const field = el(fieldId);
        field.classList.remove('error', 'success');
        if (state) field.classList.add(state);
    }

    profileForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const name = el('profile-name').value.trim();
        const phone = el('profile-phone').value.trim();
        const nameValid = name.length >= 2;
        const phoneValid = !phone || /^09\d{9}$/.test(phone);

        setFieldState('field-profile-name', nameValid ? 'success' : 'error');
        setFieldState('field-profile-phone', phoneValid ? 'success' : 'error');
        if (!nameValid || !phoneValid) {
            profileNote.className = 'form-note bad';
            profileNote.textContent = 'فیلدهای مشخص‌شده را درست کن.';
            return;
        }

        const submit = profileForm.querySelector('.submit-btn');
        submit.disabled = true;
        profileNote.className = 'form-note';
        profileNote.textContent = 'در حال ذخیره…';

        const result = await api('/api/profile', {
            method: 'POST',
            body: JSON.stringify({ name: name, phone: phone }),
        });

        submit.disabled = false;
        if (!result.ok) {
            profileNote.className = 'form-note bad';
            profileNote.textContent = result.data.error || 'ذخیره انجام نشد.';
            return;
        }

        profileNote.className = 'form-note ok';
        profileNote.textContent = 'اطلاعات حسابت ذخیره شد.';
        fillUser({ ...currentUser, name: name, phone: phone });
        toast('تغییرات حساب ذخیره شد.');
    });

    el('profile-phone').addEventListener('input', (event) => {
        event.target.value = event.target.value.replace(/[^0-9]/g, '').slice(0, 11);
    });

    /* ---------- تنظیمات: تغییر رمز ---------- */
    const passwordForm = el('password-form');
    const passwordNote = el('password-note');

    passwordForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const currentPassword = el('current-password').value;
        const newPassword = el('new-password').value;
        const confirmPassword = el('confirm-password').value;

        const currentValid = currentPassword.length > 0;
        const newValid = newPassword.length >= 8;
        const confirmValid = confirmPassword === newPassword && newPassword.length > 0;

        setFieldState('field-current-password', currentValid ? 'success' : 'error');
        setFieldState('field-new-password', newValid ? 'success' : 'error');
        setFieldState('field-confirm-password', confirmValid ? 'success' : 'error');

        if (!currentValid || !newValid || !confirmValid) {
            passwordNote.className = 'form-note bad';
            passwordNote.textContent = 'رمزها را بررسی کن؛ حداقل ۸ نویسه و تکرار یکسان.';
            return;
        }

        const submit = passwordForm.querySelector('.submit-btn');
        submit.disabled = true;
        passwordNote.className = 'form-note';
        passwordNote.textContent = 'در حال بررسی…';

        const result = await api('/api/password', {
            method: 'POST',
            body: JSON.stringify({ currentPassword: currentPassword, newPassword: newPassword }),
        });

        submit.disabled = false;
        if (!result.ok) {
            passwordNote.className = 'form-note bad';
            passwordNote.textContent = result.data.error || 'تغییر رمز انجام نشد.';
            return;
        }

        passwordForm.reset();
        ['field-current-password', 'field-new-password', 'field-confirm-password']
            .forEach((id) => setFieldState(id, null));
        passwordNote.className = 'form-note ok';
        passwordNote.textContent = 'رمز عبورت عوض شد.';
        toast('رمز عبور با موفقیت تغییر کرد.');
    });

    /* ---------- خروج ---------- */
    el('logout-btn').addEventListener('click', async () => {
        await api('/api/logout', { method: 'POST' });
        location.replace('login.html');
    });

    /* ---------- شروع ---------- */
    (async function start() {
        const me = await api('/api/me');
        if (!me.data.loggedIn) {
            location.replace('login.html');
            return;
        }
        fillUser(me.data);
        await loadBooks();
    })();
})();
