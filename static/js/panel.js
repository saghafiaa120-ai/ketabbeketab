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
    if (['overview', 'books', 'requests', 'loans', 'favorites', 'settings'].includes(initialTab)) {
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
            // نشانِ درخواست‌های در انتظار (که ویجت اعلان اضافه می‌کند) پاک نشود.
            const badge = navName.querySelector('.nav-user-badge');
            navName.textContent = name;
            if (badge) navName.appendChild(badge);
            navName.href = '/panel.html';
        }

        const adminLink = el('admin-link');
        if (adminLink) adminLink.hidden = !user.isAdmin;

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

    /* ---------- درخواست‌های امانت / خرید ---------- */
    const requestStatusLabels = {
        pending: 'در انتظار پاسخ',
        accepted: 'تأیید شد',
        coordinating: 'در حال هماهنگی',
        delivered: 'تحویل‌شده',
        on_loan: 'در حال امانت',
        returned: 'بازگشت داده شد',
        completed: 'خرید تکمیل شد',
        rejected: 'رد شد',
        cancelled: 'لغو شد',
    };

    const stepLabels = {
        accepted: 'تأیید',
        coordinating: 'هماهنگی',
        delivered: 'تحویل',
        on_loan: 'در حال امانت',
        returned: 'بازگشت',
        completed: 'تکمیل',
    };

    function faDate(value) {
        if (!value) return '';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '';
        try {
            return new Intl.DateTimeFormat('fa-IR', { day: 'numeric', month: 'short' }).format(date);
        } catch (error) {
            return '';
        }
    }

    function faFullDate(value) {
        if (!value) return '';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '';
        try {
            return new Intl.DateTimeFormat('fa-IR', {
                day: 'numeric', month: 'long', year: 'numeric',
            }).format(date);
        } catch (error) {
            return '';
        }
    }

    function requestMeta(req) {
        const parts = [req.shareTypeLabel || req.shareType];
        if (req.amount) parts.push(toFa(req.amount.toLocaleString('en-US')) + ' تومان');
        return parts.join(' • ');
    }

    /* نوار پیشرفت امانت: تأیید ← هماهنگی ← تحویل ← در حال امانت ← بازگشت */
    function timeline(req) {
        if (!req.steps || !req.currentStep) return null;

        const box = document.createElement('div');
        box.className = 'loan-track';

        req.steps.forEach((step, index) => {
            const item = document.createElement('span');
            item.className = 'loan-step';
            if (index + 1 < req.currentStep) item.classList.add('done');
            if (index + 1 === req.currentStep) item.classList.add('current');
            item.textContent = stepLabels[step] || step;
            box.appendChild(item);
        });

        return box;
    }

    function dueLine(req) {
        if (!req.dueAt) return null;
        const line = document.createElement('p');
        line.className = 'loan-due';

        const parts = ['موعد بازگشت: ' + faFullDate(req.dueAt)];
        if (req.deliveredAt) parts.unshift('تحویل: ' + faFullDate(req.deliveredAt));

        if (req.status === 'on_loan' && typeof req.daysLeft === 'number') {
            if (req.daysLeft < 0) {
                line.classList.add('overdue');
                parts.push(toFa(Math.abs(req.daysLeft)) + ' روز تأخیر');
            } else if (req.daysLeft === 0) {
                line.classList.add('soon');
                parts.push('امروز آخرین روز است');
            } else if (req.daysLeft <= 3) {
                line.classList.add('soon');
                parts.push(toFa(req.daysLeft) + ' روز مانده');
            }
        }

        line.textContent = parts.join(' · ');
        return line;
    }

    async function changeRequestStatus(req, status, button) {
        const label = button.textContent;
        button.disabled = true;
        button.textContent = 'در حال ثبت…';

        const result = await api(`/api/requests/${req.id}/status`, {
            method: 'POST',
            body: JSON.stringify({ status: status }),
        });

        if (!result.ok) {
            button.disabled = false;
            button.textContent = label;
            toast(result.data.error || 'تغییر وضعیت انجام نشد.', true);
            return;
        }

        toast('وضعیت به «' + (result.data.statusLabel || requestStatusLabels[status] || status) + '» تغییر کرد.');
        await loadRequests();
        await loadLoans();
    }

    function requestRow(req, box) {
        const row = document.createElement('article');
        row.className = 'request-row';
        if (req.isOverdue) row.classList.add('is-overdue');

        const info = document.createElement('div');
        info.className = 'request-main';

        const head = document.createElement('div');
        head.className = 'request-head';

        const title = document.createElement('a');
        title.className = 'request-title';
        title.href = req.bookDetailUrl;
        title.textContent = req.bookTitle || 'کتاب';

        const chip = document.createElement('span');
        chip.className = 'status-chip ' + req.status;
        chip.textContent = requestStatusLabels[req.status] || req.status;

        head.append(title, chip);

        const who = document.createElement('p');
        who.className = 'request-sub';
        if (box === 'incoming') {
            who.textContent = `درخواست‌دهنده: ${req.requesterName || 'کاربر'} · ${faDate(req.createdAt)}`;
        } else if (box === 'loans') {
            who.textContent = req.role === 'owner'
                ? `امانت‌گیرنده: ${req.requesterName || 'کاربر'}`
                : `صاحب کتاب: ${req.ownerName || 'کاربر'}`;
        } else {
            who.textContent = `صاحب کتاب: ${req.ownerName || 'کاربر'} · ${faDate(req.createdAt)}`;
        }

        const meta = document.createElement('p');
        meta.className = 'request-sub request-meta';
        meta.textContent = requestMeta(req);

        info.append(head, who, meta);

        const track = timeline(req);
        if (track) info.appendChild(track);

        const due = dueLine(req);
        if (due) info.appendChild(due);

        if (req.message) {
            const msg = document.createElement('p');
            msg.className = 'request-message';
            msg.textContent = '«' + req.message + '»';
            info.appendChild(msg);
        }

        row.appendChild(info);

        const actions = req.actions || [];
        if (actions.length) {
            const actionBox = document.createElement('div');
            actionBox.className = 'request-actions';

            actions.forEach((action) => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'req-btn ' + (action.style || 'ghost');
                button.textContent = action.label;
                button.addEventListener('click', () => changeRequestStatus(req, action.status, button));
                actionBox.appendChild(button);
            });

            row.appendChild(actionBox);
        }

        return row;
    }

    function renderRequestList(container, items, box, emptyText) {
        container.textContent = '';
        if (!items.length) {
            const empty = document.createElement('p');
            empty.className = 'panel-empty';
            empty.textContent = emptyText;
            container.appendChild(empty);
            return;
        }
        items.forEach((req) => container.appendChild(requestRow(req, box)));
    }

    function renderRequestBadges(pendingIncoming) {
        const badge = el('requests-badge');
        if (badge) {
            badge.textContent = toFa(pendingIncoming);
            badge.style.display = pendingIncoming ? 'inline-block' : 'none';
        }

        const notice = el('requests-notice');
        const noticeText = el('requests-notice-text');
        if (notice && noticeText) {
            notice.hidden = pendingIncoming === 0;
            noticeText.textContent = pendingIncoming
                ? `${toFa(pendingIncoming)} درخواست جدید برای کتاب‌هایت داری`
                : '';
        }
    }

    async function loadRequests() {
        const incomingList = el('incoming-list');
        const outgoingList = el('outgoing-list');
        const result = await api('/api/requests');

        if (result.status === 401) {
            location.replace('login.html');
            return;
        }
        if (!result.ok) {
            toast(result.data.error || 'دریافت درخواست‌ها انجام نشد.', true);
            return;
        }

        const incoming = result.data.incoming || [];
        const outgoing = result.data.outgoing || [];
        const pendingIncoming = result.data.pendingIncoming || 0;

        renderRequestList(incomingList, incoming, 'incoming', 'هنوز درخواستی برای کتاب‌هایت ثبت نشده است.');
        renderRequestList(outgoingList, outgoing, 'outgoing', 'هنوز درخواستی برای کتابی نفرستاده‌ای.');

        const incomingMeta = el('incoming-meta');
        if (incomingMeta) {
            incomingMeta.textContent = pendingIncoming
                ? `${toFa(pendingIncoming)} در انتظار پاسخ`
                : (incoming.length ? 'همه بررسی شده‌اند' : '‌');
        }

        const outgoingMeta = el('outgoing-meta');
        if (outgoingMeta) {
            outgoingMeta.textContent = outgoing.length ? `${toFa(outgoing.length)} درخواست` : '‌';
        }

        renderRequestBadges(pendingIncoming);
    }

    /* ---------- پیگیری امانت ---------- */
    function renderLoanSummary(active, overdueCount, dueSoonCount) {
        const box = el('loan-summary');
        if (!box) return;

        box.textContent = '';
        if (!active.length) {
            box.hidden = true;
            return;
        }

        const cards = [
            { label: 'امانت فعال', value: active.length, tone: 'teal' },
            { label: 'نزدیک موعد', value: dueSoonCount, tone: 'gold' },
            { label: 'تأخیر', value: overdueCount, tone: 'red' },
        ];

        cards.forEach((card) => {
            const item = document.createElement('div');
            item.className = 'loan-sum ' + card.tone;

            const value = document.createElement('strong');
            value.textContent = toFa(card.value);

            const label = document.createElement('span');
            label.textContent = card.label;

            item.append(value, label);
            box.appendChild(item);
        });

        box.hidden = false;
    }

    function renderLoanList(container, items, box, emptyText) {
        container.textContent = '';
        if (!items.length) {
            const empty = document.createElement('p');
            empty.className = 'panel-empty';
            empty.textContent = emptyText;
            container.appendChild(empty);
            return;
        }
        items.forEach((req) => container.appendChild(requestRow(req, box)));
    }

    function renderDueNotice(active, overdueCount, dueSoonCount) {
        const notice = el('due-notice');
        const text = el('due-notice-text');
        if (!notice || !text) return;

        if (overdueCount) {
            text.textContent = `${toFa(overdueCount)} امانت از موعد گذشته است`;
            notice.hidden = false;
        } else if (dueSoonCount) {
            text.textContent = `${toFa(dueSoonCount)} امانت نزدیک موعد بازگشت است`;
            notice.hidden = false;
        } else {
            notice.hidden = true;
        }

        const badge = el('loans-badge');
        if (badge) {
            badge.textContent = toFa(active.length);
            badge.style.display = active.length ? 'inline-block' : 'none';
        }
    }

    async function loadLoans() {
        const activeList = el('loans-active-list');
        const historyList = el('loans-history-list');
        const result = await api('/api/loans');

        if (result.status === 401) return;
        if (!result.ok) {
            toast(result.data.error || 'دریافت امانت‌ها انجام نشد.', true);
            return;
        }

        const active = result.data.active || [];
        const history = result.data.history || [];
        const overdueCount = result.data.overdueCount || 0;
        const dueSoonCount = result.data.dueSoonCount || 0;

        renderLoanSummary(active, overdueCount, dueSoonCount);
        renderLoanList(activeList, active, 'loans', 'الان امانت فعالی نداری.');
        renderLoanList(historyList, history, 'loans', 'هنوز امانت یا خریدی کامل نشده است.');

        const meta = el('loans-meta');
        if (meta) {
            meta.textContent = active.length ? `${toFa(active.length)} در جریان` : '‌';
        }

        const historyMeta = el('loans-history-meta');
        if (historyMeta) {
            historyMeta.textContent = history.length ? `${toFa(history.length)} مورد` : '‌';
        }

        renderDueNotice(active, overdueCount, dueSoonCount);
    }

    /* ---------- علاقه‌مندی‌ها ---------- */
    function favoriteCard(book) {
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

        const rating = document.createElement('p');
        rating.className = 'fav-rating';
        rating.textContent = book.ratingCount
            ? '★ ' + toFa(book.ratingAvg) + ' از ۵ · ' + toFa(book.ratingCount) + ' نظر'
            : 'بدون امتیاز';

        const actions = document.createElement('div');
        actions.className = 'my-book-actions';

        const detail = document.createElement('a');
        detail.href = book.detailUrl || '/books.html';
        detail.textContent = 'مشاهده';
        actions.appendChild(detail);

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = 'برداشتن';
        remove.addEventListener('click', async () => {
            remove.disabled = true;
            const result = await api('/api/books/' + book.id + '/favorite', { method: 'POST' });
            if (!result.ok) {
                remove.disabled = false;
                toast(result.data.error || 'انجام نشد.', true);
                return;
            }
            toast('از علاقه‌مندی‌ها برداشته شد.');
            loadFavorites();
        });
        actions.appendChild(remove);

        body.append(title, author, rating, actions);
        card.append(cover, body);
        return card;
    }

    async function loadFavorites() {
        const grid = el('favorites-grid');
        const empty = el('favorites-empty');
        const result = await api('/api/favorites');

        if (result.status === 401) return;
        if (!result.ok) {
            toast(result.data.error || 'دریافت علاقه‌مندی‌ها انجام نشد.', true);
            return;
        }

        const books = Array.isArray(result.data) ? result.data : [];
        grid.textContent = '';
        books.forEach((book) => grid.appendChild(favoriteCard(book)));
        empty.hidden = books.length > 0;

        const badge = el('favorites-badge');
        if (badge) {
            badge.textContent = toFa(books.length);
            badge.style.display = books.length ? 'inline-block' : 'none';
        }

        const meta = el('favorites-meta');
        if (meta) {
            meta.textContent = books.length ? `${toFa(books.length)} کتاب` : '‌';
        }
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
        await loadRequests();
        await loadLoans();
        await loadFavorites();
    })();
})();
