/* =========================================================
   پنل مدیریت کتاب‌به‌کتاب
   - گارد دسترسی (فقط is_admin)
   - کاربران، کتاب‌ها، نظرات، درخواست‌ها
========================================================= */
(function () {
    'use strict';

    const faDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
    const el = (id) => document.getElementById(id);
    const toFa = (value) => String(value).replace(/\d/g, (d) => faDigits[Number(d)]);

    const GENRES = [
        ['novel', 'رمان'], ['story', 'داستان کوتاه'], ['poetry', 'شعر و ادبیات'],
        ['history', 'تاریخ'], ['science', 'علمی'], ['kids', 'کودک و نوجوان'], ['other', 'سایر'],
    ];
    const CONDITIONS = [['new', 'نو'], ['like-new', 'در حد نو'], ['good', 'قابل قبول']];
    const SHARE_TYPES = [['free', 'امانت رایگان'], ['deposit', 'امانت با ودیعه'], ['sale', 'فروش']];
    const STATUS_LABELS = {
        pending: 'در انتظار پاسخ', accepted: 'تأیید شد', coordinating: 'در حال هماهنگی',
        delivered: 'تحویل‌شده', on_loan: 'در حال امانت', returned: 'بازگشت داده شد',
        completed: 'خرید تکمیل شد', rejected: 'رد شد', cancelled: 'لغو شد',
    };

    /* ---------- شبکه ---------- */
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

    /* ---------- تاریخ ---------- */
    function faDate(value) {
        if (!value) return '—';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '—';
        try {
            return new Intl.DateTimeFormat('fa-IR', { day: 'numeric', month: 'short', year: 'numeric' }).format(date);
        } catch (error) {
            return '—';
        }
    }

    function faDateTime(value) {
        if (!value) return '—';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '—';
        try {
            return new Intl.DateTimeFormat('fa-IR', {
                day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
            }).format(date);
        } catch (error) {
            return '—';
        }
    }

    const initials = (name) => {
        const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return '؟';
        return (parts[0].charAt(0) + (parts[1] ? parts[1].charAt(0) : '')).toUpperCase();
    };

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
        if (location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
    }

    navItems.forEach((item) => item.addEventListener('click', () => showTab(item.dataset.tab)));
    document.querySelectorAll('[data-goto]').forEach((btn) => {
        btn.addEventListener('click', () => showTab(btn.dataset.goto));
    });

    const initialTab = (location.hash || '').replace('#', '');
    if (['overview', 'users', 'books', 'reviews', 'requests'].includes(initialTab)) {
        showTab(initialTab);
    }

    /* ---------- منوی موبایل و انیمیشن ---------- */
    document.querySelector('.menu-btn')?.addEventListener('click', () => {
        const button = document.querySelector('.menu-btn');
        const nav = document.querySelector('.nav-links');
        const open = nav.classList.toggle('open');
        button.setAttribute('aria-expanded', String(open));
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
        }, { threshold: 0.08 });
        revealEls.forEach((node) => io.observe(node));
    } else {
        revealEls.forEach((node) => node.classList.add('visible'));
    }

    const dateChip = el('admin-date');
    if (dateChip) {
        try {
            dateChip.textContent = new Intl.DateTimeFormat('fa-IR', {
                weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
            }).format(new Date());
        } catch (error) {
            dateChip.textContent = '';
        }
    }

    /* ---------- مودال ---------- */
    const modal = el('admin-modal');
    const modalTitle = el('modal-title');
    const modalForm = el('modal-form');
    const modalNote = el('modal-note');
    let modalSubmit = null;

    function closeModal() {
        modal.hidden = true;
        modalForm.textContent = '';
        modalNote.textContent = '';
        modalNote.className = 'admin-form-note';
    }

    el('modal-close').addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) closeModal();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !modal.hidden) closeModal();
    });

    function openModal(title, fields, onSubmit, submitLabel) {
        modalTitle.textContent = title;
        modalNote.textContent = '';
        modalNote.className = 'admin-form-note';
        modalForm.textContent = '';

        fields.forEach((field) => {
            if (field.type === 'row') {
                const row = document.createElement('div');
                row.className = 'admin-form-row';
                field.fields.forEach((inner) => row.appendChild(buildField(inner)));
                modalForm.appendChild(row);
                return;
            }
            modalForm.appendChild(buildField(field));
        });

        const actions = document.createElement('div');
        actions.className = 'admin-form-actions';

        const save = document.createElement('button');
        save.type = 'submit';
        save.className = 'admin-save';
        save.textContent = submitLabel || 'ذخیره';
        actions.appendChild(save);

        modalForm.appendChild(actions);
        modalSubmit = { save, onSubmit };
        modal.hidden = false;
        const first = modalForm.querySelector('input, textarea, select');
        if (first) first.focus();
    }

    function buildField(field) {
        if (field.type === 'checkbox') {
            const label = document.createElement('label');
            label.className = 'admin-check';
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.name = field.name;
            input.checked = Boolean(field.value);
            const text = document.createElement('span');
            text.textContent = field.label;
            label.append(input, text);
            return label;
        }

        const label = document.createElement('label');
        label.textContent = field.label;

        let input;
        if (field.type === 'select') {
            input = document.createElement('select');
            field.options.forEach(([value, text]) => {
                const option = document.createElement('option');
                option.value = value;
                option.textContent = text;
                if (String(field.value) === String(value)) option.selected = true;
                input.appendChild(option);
            });
        } else if (field.type === 'textarea') {
            input = document.createElement('textarea');
            input.value = field.value || '';
        } else {
            input = document.createElement('input');
            input.type = field.type || 'text';
            input.value = field.value === null || field.value === undefined ? '' : field.value;
        }

        input.name = field.name;
        if (field.placeholder) input.placeholder = field.placeholder;
        if (field.required) input.required = true;
        label.appendChild(input);
        return label;
    }

    modalForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!modalSubmit) return;

        const values = {};
        Array.from(modalForm.elements).forEach((input) => {
            if (!input.name) return;
            values[input.name] = input.type === 'checkbox' ? input.checked : input.value.trim();
        });

        modalSubmit.save.disabled = true;
        const original = modalSubmit.save.textContent;
        modalSubmit.save.textContent = 'در حال ذخیره…';

        const result = await modalSubmit.onSubmit(values);

        modalSubmit.save.disabled = false;
        modalSubmit.save.textContent = original;

        if (result && result.ok) {
            closeModal();
            toast(result.message || 'ذخیره شد.');
        } else {
            modalNote.className = 'admin-form-note bad';
            modalNote.textContent = (result && result.error) || 'ذخیره انجام نشد.';
        }
    });

    /* ---------- نمای کلی ---------- */
    function emptyRow(text) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 6;
        cell.className = 'admin-empty';
        cell.textContent = text;
        row.appendChild(cell);
        return row;
    }

    function compactItem({ avatar, title, subtitle, side }) {
        const item = document.createElement('div');
        item.className = 'admin-item';

        if (avatar) {
            const badge = document.createElement('span');
            badge.className = 'admin-avatar-sm';
            badge.textContent = avatar;
            item.appendChild(badge);
        }

        const main = document.createElement('div');
        main.className = 'admin-item-main';

        const strong = document.createElement('strong');
        strong.textContent = title;
        main.appendChild(strong);

        if (subtitle) {
            const span = document.createElement('span');
            span.textContent = subtitle;
            main.appendChild(span);
        }

        item.appendChild(main);

        if (side) {
            const sideBox = document.createElement('div');
            sideBox.className = 'admin-item-side';
            sideBox.textContent = side;
            item.appendChild(sideBox);
        }

        return item;
    }

    async function loadOverview() {
        const result = await api('/api/admin/overview');
        if (!result.ok) return;
        const { stats, recentUsers, recentBooks, recentReviews } = result.data;

        el('stat-users').textContent = toFa(stats.users || 0);
        el('stat-active').textContent = toFa(stats.active_users || 0) + ' فعال در ۷ روز اخیر';
        el('stat-books').textContent = toFa(stats.books || 0);
        el('stat-requests').textContent = toFa(stats.requests || 0);
        el('stat-pending').textContent = toFa(stats.pending || 0) + ' در انتظار پاسخ';
        el('stat-loans').textContent = toFa(stats.on_loan || 0);
        el('stat-reviews').textContent = toFa(stats.reviews || 0);
        el('stat-favorites').textContent = toFa(stats.favorites || 0);

        el('users-badge').textContent = toFa(stats.users || 0);
        el('books-badge').textContent = toFa(stats.books || 0);
        el('reviews-badge').textContent = toFa(stats.reviews || 0);
        el('requests-badge').textContent = toFa(stats.pending || 0);

        const usersBox = el('recent-users');
        usersBox.textContent = '';
        if (!recentUsers.length) {
            usersBox.innerHTML = '<p class="panel-empty">هنوز کاربری ثبت‌نام نکرده است.</p>';
        }
        recentUsers.forEach((user) => usersBox.appendChild(compactItem({
            avatar: initials(user.name),
            title: user.name,
            subtitle: user.email,
            side: user.lastLoginAt ? faDateTime(user.lastLoginAt) : 'هنوز وارد نشده',
        })));

        const booksBox = el('recent-books');
        booksBox.textContent = '';
        if (!recentBooks.length) {
            booksBox.innerHTML = '<p class="panel-empty">کتابی ثبت نشده است.</p>';
        }
        recentBooks.forEach((book) => booksBox.appendChild(compactItem({
            title: book.title,
            subtitle: 'صاحب: ' + book.ownerName,
            side: faDate(book.createdAt),
        })));

        const reviewsBox = el('recent-reviews');
        reviewsBox.textContent = '';
        if (!recentReviews.length) {
            reviewsBox.innerHTML = '<p class="panel-empty">نظری ثبت نشده است.</p>';
        }
        recentReviews.forEach((review) => reviewsBox.appendChild(compactItem({
            title: '★ ' + toFa(review.rating) + ' — ' + review.bookTitle,
            subtitle: (review.comment || 'بدون متن') + ' · ' + review.userName,
            side: faDate(review.createdAt),
        })));
    }

    /* ---------- کاربران ---------- */
    let usersCache = [];

    async function loadUsers(query = '') {
        const result = await api('/api/admin/users?q=' + encodeURIComponent(query));
        const body = el('users-body');
        body.textContent = '';

        if (!result.ok) {
            body.appendChild(emptyRow(result.data.error || 'دریافت کاربران انجام نشد.'));
            return;
        }

        usersCache = result.data;
        el('users-meta').textContent = usersCache.length ? toFa(usersCache.length) + ' کاربر' : '‌';

        if (!usersCache.length) {
            body.appendChild(emptyRow('کاربری پیدا نشد.'));
            return;
        }

        usersCache.forEach((user) => {
            const row = document.createElement('tr');

            const info = document.createElement('td');
            const main = document.createElement('div');
            main.className = 'admin-cell-main';
            const name = document.createElement('strong');
            name.textContent = user.name + (user.isMe ? ' (خودت)' : '');
            const email = document.createElement('span');
            email.textContent = user.email;
            main.append(name, email);
            info.appendChild(main);

            const phone = document.createElement('td');
            phone.textContent = user.phone || '—';

            const login = document.createElement('td');
            login.className = 'admin-date-cell';
            login.textContent = user.lastLoginAt
                ? faDateTime(user.lastLoginAt) + ' · ' + toFa(user.loginCount) + ' بار'
                : 'هنوز وارد نشده';

            const counts = document.createElement('td');
            counts.textContent = toFa(user.bookCount) + ' / ' + toFa(user.requestCount) + ' / ' + toFa(user.reviewCount);

            const role = document.createElement('td');
            const pill = document.createElement('span');
            pill.className = 'admin-pill' + (user.isAdmin ? ' admin' : '');
            pill.textContent = user.isAdmin ? 'مدیر' : 'کاربر';
            role.appendChild(pill);

            const actions = document.createElement('td');
            const box = document.createElement('div');
            box.className = 'admin-actions';

            const edit = document.createElement('button');
            edit.type = 'button';
            edit.className = 'admin-btn';
            edit.textContent = 'ویرایش';
            edit.addEventListener('click', () => editUser(user));
            box.appendChild(edit);

            const pass = document.createElement('button');
            pass.type = 'button';
            pass.className = 'admin-btn';
            pass.textContent = 'رمز';
            pass.addEventListener('click', () => resetPassword(user));
            box.appendChild(pass);

            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'admin-btn danger';
            remove.textContent = 'حذف';
            remove.addEventListener('click', () => deleteUser(user, remove));
            box.appendChild(remove);

            actions.appendChild(box);

            row.append(info, phone, login, counts, role, actions);
            body.appendChild(row);
        });
    }

    function editUser(user) {
        openModal('ویرایش کاربر', [
            { name: 'name', label: 'نام', value: user.name, required: true },
            { name: 'email', label: 'ایمیل', type: 'email', value: user.email, required: true },
            { name: 'phone', label: 'شماره موبایل', value: user.phone || '', placeholder: '09xxxxxxxxx' },
            { name: 'isAdmin', label: 'دسترسی مدیریت', type: 'checkbox', value: user.isAdmin },
        ], async (values) => {
            const result = await api('/api/admin/users/' + user.id, {
                method: 'POST',
                body: JSON.stringify(values),
            });
            if (result.ok) {
                loadUsers(el('users-search').value.trim());
                loadOverview();
            }
            return { ok: result.ok, error: result.data.error };
        });
    }

    async function resetPassword(user) {
        const password = window.prompt('رمز جدید برای «' + user.name + '» (حداقل ۸ نویسه):');
        if (!password) return;
        if (password.length < 8) {
            toast('رمز باید حداقل ۸ نویسه باشد.', true);
            return;
        }
        const result = await api('/api/admin/users/' + user.id + '/password', {
            method: 'POST',
            body: JSON.stringify({ password }),
        });
        toast(result.ok ? 'رمز کاربر عوض شد.' : (result.data.error || 'تغییر رمز انجام نشد.'), !result.ok);
    }

    async function deleteUser(user, button) {
        const warning = 'کاربر «' + user.name + '» و همه‌ی کتاب‌ها، درخواست‌ها، نظرات و علاقه‌مندی‌هایش حذف می‌شود. مطمئنی؟';
        if (!window.confirm(warning)) return;

        button.disabled = true;
        const result = await api('/api/admin/users/' + user.id, { method: 'DELETE' });
        if (!result.ok) {
            button.disabled = false;
            toast(result.data.error || 'حذف انجام نشد.', true);
            return;
        }
        toast('کاربر حذف شد.');
        loadUsers(el('users-search').value.trim());
        loadOverview();
    }

    /* ---------- کتاب‌ها ---------- */
    let booksCache = [];

    async function loadBooks(query = '') {
        const result = await api('/api/admin/books?q=' + encodeURIComponent(query));
        const body = el('books-body');
        body.textContent = '';

        if (!result.ok) {
            body.appendChild(emptyRow(result.data.error || 'دریافت کتاب‌ها انجام نشد.'));
            return;
        }

        booksCache = result.data;
        el('books-meta').textContent = booksCache.length ? toFa(booksCache.length) + ' کتاب' : '‌';

        if (!booksCache.length) {
            body.appendChild(emptyRow('کتابی پیدا نشد.'));
            return;
        }

        booksCache.forEach((book) => {
            const row = document.createElement('tr');

            const info = document.createElement('td');
            const main = document.createElement('div');
            main.className = 'admin-cell-main';
            const title = document.createElement('strong');
            title.textContent = book.title;
            const sub = document.createElement('span');
            sub.textContent = book.author + ' · ' + book.genreLabel + ' · ' + book.conditionLabel;
            main.append(title, sub);
            info.appendChild(main);

            const owner = document.createElement('td');
            owner.textContent = book.ownerName;

            const type = document.createElement('td');
            const pill = document.createElement('span');
            pill.className = 'admin-pill';
            pill.textContent = book.shareTypeLabel;
            type.appendChild(pill);

            const counts = document.createElement('td');
            counts.textContent = toFa(book.requestCount) + ' / ' + toFa(book.reviewCount);

            const date = document.createElement('td');
            date.className = 'admin-date-cell';
            date.textContent = faDate(book.createdAt);

            const actions = document.createElement('td');
            const box = document.createElement('div');
            box.className = 'admin-actions';

            const open = document.createElement('a');
            open.className = 'admin-btn';
            open.href = book.detailUrl;
            open.target = '_blank';
            open.rel = 'noopener';
            open.textContent = 'صفحه';
            box.appendChild(open);

            const edit = document.createElement('button');
            edit.type = 'button';
            edit.className = 'admin-btn';
            edit.textContent = 'ویرایش';
            edit.addEventListener('click', () => editBook(book));
            box.appendChild(edit);

            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'admin-btn danger';
            remove.textContent = 'حذف';
            remove.addEventListener('click', () => deleteBook(book, remove));
            box.appendChild(remove);

            actions.appendChild(box);
            row.append(info, owner, type, counts, date, actions);
            body.appendChild(row);
        });
    }

    function editBook(book) {
        openModal('ویرایش کتاب', [
            { name: 'title', label: 'عنوان', value: book.title, required: true },
            { name: 'author', label: 'نویسنده', value: book.author, required: true },
            {
                type: 'row', fields: [
                    { name: 'genre', label: 'ژانر', type: 'select', options: GENRES, value: book.genre },
                    { name: 'condition', label: 'وضعیت', type: 'select', options: CONDITIONS, value: book.condition },
                ],
            },
            {
                type: 'row', fields: [
                    { name: 'shareType', label: 'نوع اشتراک', type: 'select', options: SHARE_TYPES, value: book.shareType },
                    { name: 'duration', label: 'مدت امانت (روز)', type: 'number', value: book.duration || '' },
                ],
            },
            {
                type: 'row', fields: [
                    { name: 'depositAmount', label: 'ودیعه (تومان)', type: 'number', value: book.depositAmount || '' },
                    { name: 'salePrice', label: 'قیمت فروش (تومان)', type: 'number', value: book.salePrice || '' },
                ],
            },
            { name: 'address', label: 'محل تحویل', value: book.address, required: true },
            { name: 'description', label: 'توضیحات', type: 'textarea', value: book.description || '' },
        ], async (values) => {
            const result = await api('/api/admin/books/' + book.id, {
                method: 'POST',
                body: JSON.stringify(values),
            });
            if (result.ok) {
                loadBooks(el('books-search').value.trim());
                loadOverview();
            }
            return { ok: result.ok, error: result.data.error };
        });
    }

    async function deleteBook(book, button) {
        if (!window.confirm('کتاب «' + book.title + '» و درخواست‌ها و نظراتش حذف شود؟ این کار برگشت‌پذیر نیست.')) return;

        button.disabled = true;
        const result = await api('/api/books/' + book.id, { method: 'DELETE' });
        if (!result.ok) {
            button.disabled = false;
            toast(result.data.error || 'حذف انجام نشد.', true);
            return;
        }
        toast('کتاب حذف شد.');
        loadBooks(el('books-search').value.trim());
        loadOverview();
    }

    /* ---------- نظرات ---------- */
    async function loadReviews(query = '') {
        const result = await api('/api/admin/reviews?q=' + encodeURIComponent(query));
        const box = el('reviews-list');
        box.textContent = '';

        if (!result.ok) {
            box.innerHTML = '<p class="panel-empty">دریافت نظرات انجام نشد.</p>';
            return;
        }

        const items = result.data;
        el('reviews-meta').textContent = items.length ? toFa(items.length) + ' نظر' : '‌';

        if (!items.length) {
            box.innerHTML = '<p class="panel-empty">نظری ثبت نشده است.</p>';
            return;
        }

        items.forEach((review) => {
            const card = document.createElement('article');
            card.className = 'admin-item';

            const main = document.createElement('div');
            main.className = 'admin-item-main';

            const title = document.createElement('strong');
            title.textContent = '★ ' + toFa(review.rating) + ' — ' + review.bookTitle;

            const who = document.createElement('span');
            who.textContent = review.userName + ' · ' + review.userEmail + ' · ' + faDate(review.createdAt);

            main.append(title, who);

            if (review.comment) {
                const text = document.createElement('span');
                text.textContent = review.comment;
                text.style.color = 'var(--ink)';
                main.appendChild(text);
            }

            const side = document.createElement('div');
            side.className = 'admin-item-side';

            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'admin-btn danger';
            remove.textContent = 'حذف نظر';
            remove.addEventListener('click', async () => {
                if (!window.confirm('این نظر حذف شود؟')) return;
                remove.disabled = true;
                const res = await api('/api/admin/reviews/' + review.id, { method: 'DELETE' });
                if (!res.ok) {
                    remove.disabled = false;
                    toast(res.data.error || 'حذف انجام نشد.', true);
                    return;
                }
                toast('نظر حذف شد.');
                loadReviews(el('reviews-search').value.trim());
                loadOverview();
            });
            side.appendChild(remove);

            card.append(main, side);
            box.appendChild(card);
        });
    }

    /* ---------- درخواست‌ها ---------- */
    async function loadRequests(status = '') {
        const result = await api('/api/admin/requests?status=' + encodeURIComponent(status));
        const body = el('requests-body');
        body.textContent = '';

        if (!result.ok) {
            body.appendChild(emptyRow(result.data.error || 'دریافت درخواست‌ها انجام نشد.'));
            return;
        }

        const items = result.data;
        el('requests-meta').textContent = items.length ? toFa(items.length) + ' درخواست' : '‌';

        if (!items.length) {
            body.appendChild(emptyRow('درخواستی پیدا نشد.'));
            return;
        }

        items.forEach((req) => {
            const row = document.createElement('tr');

            const book = document.createElement('td');
            const main = document.createElement('div');
            main.className = 'admin-cell-main';
            const title = document.createElement('strong');
            title.textContent = req.bookTitle;
            const sub = document.createElement('span');
            sub.textContent = req.shareTypeLabel;
            main.append(title, sub);
            book.appendChild(main);

            const requester = document.createElement('td');
            requester.textContent = req.requesterName;

            const owner = document.createElement('td');
            owner.textContent = req.ownerName;

            const statusCell = document.createElement('td');
            const select = document.createElement('select');
            select.className = 'admin-input admin-select';
            select.style.minWidth = '150px';
            Object.entries(STATUS_LABELS).forEach(([value, label]) => {
                const option = document.createElement('option');
                option.value = value;
                option.textContent = label;
                if (value === req.status) option.selected = true;
                select.appendChild(option);
            });
            select.addEventListener('change', async () => {
                const res = await api('/api/admin/requests/' + req.id, {
                    method: 'POST',
                    body: JSON.stringify({ status: select.value }),
                });
                if (!res.ok) {
                    toast(res.data.error || 'تغییر وضعیت انجام نشد.', true);
                    select.value = req.status;
                    return;
                }
                toast('وضعیت به «' + (res.data.statusLabel || select.value) + '» تغییر کرد.');
                loadOverview();
            });
            statusCell.appendChild(select);

            const date = document.createElement('td');
            date.className = 'admin-date-cell';
            date.textContent = faDate(req.createdAt);

            const actions = document.createElement('td');
            const box = document.createElement('div');
            box.className = 'admin-actions';

            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'admin-btn danger';
            remove.textContent = 'حذف';
            remove.addEventListener('click', async () => {
                if (!window.confirm('این درخواست حذف شود؟')) return;
                remove.disabled = true;
                const res = await api('/api/admin/requests/' + req.id, { method: 'DELETE' });
                if (!res.ok) {
                    remove.disabled = false;
                    toast(res.data.error || 'حذف انجام نشد.', true);
                    return;
                }
                toast('درخواست حذف شد.');
                loadRequests(el('requests-filter').value);
                loadOverview();
            });
            box.appendChild(remove);
            actions.appendChild(box);

            row.append(book, requester, owner, statusCell, date, actions);
            body.appendChild(row);
        });
    }

    /* ---------- جست‌وجو با تأخیر ---------- */
    function debounce(fn, delay = 350) {
        let timer = null;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    }

    el('users-search').addEventListener('input', debounce((event) => loadUsers(event.target.value.trim())));
    el('books-search').addEventListener('input', debounce((event) => loadBooks(event.target.value.trim())));
    el('reviews-search').addEventListener('input', debounce((event) => loadReviews(event.target.value.trim())));
    el('requests-filter').addEventListener('change', (event) => loadRequests(event.target.value));

    /* ---------- خروج ---------- */
    el('logout-btn').addEventListener('click', async () => {
        await api('/api/logout', { method: 'POST' });
        location.replace('/login.html');
    });

    /* ---------- شروع ---------- */
    (async function start() {
        const me = await api('/api/me');

        if (!me.data.loggedIn) {
            location.replace('/login.html');
            return;
        }
        if (!me.data.isAdmin) {
            location.replace('/panel.html');
            return;
        }

        el('admin-avatar').textContent = initials(me.data.name);
        el('admin-name').textContent = me.data.name || 'مدیر';
        el('admin-email').textContent = me.data.email || '';

        const navName = el('nav-user-name');
        if (navName) {
            navName.textContent = me.data.name || 'پنل کاربری';
            navName.href = '/panel.html';
        }

        await loadOverview();
        await loadUsers();
        await loadBooks();
        await loadReviews();
        await loadRequests();
    })();
})();
