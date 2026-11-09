/* =========================================================
   اعلان‌های داخل سایت — کتاب‌به‌کتاب
   این فایل در همه‌ی صفحه‌ها بارگذاری می‌شود و اگر کاربر وارد شده باشد،
   زنگ اعلان را کنار دکمه‌ی حساب در هدر می‌سازد.
   - درخواست جدید، تأیید/رد، تغییر وضعیت امانت، نزدیک‌شدن موعد بازگشت
========================================================= */
(function () {
    'use strict';

    const faDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
    const toFa = (value) => String(value).replace(/\d/g, (d) => faDigits[Number(d)]);
    const POLL_MS = 45000;

    function ensureStyles() {
        if (document.querySelector('link[data-notifications-css]')) return;
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/static/css/notifications.css';
        link.dataset.notificationsCss = '1';
        document.head.appendChild(link);
    }

    function relativeTime(iso) {
        if (!iso) return '';
        const then = new Date(iso);
        if (Number.isNaN(then.getTime())) return '';
        const minutes = Math.round((Date.now() - then.getTime()) / 60000);
        if (minutes < 1) return 'همین حالا';
        if (minutes < 60) return toFa(minutes) + ' دقیقه پیش';
        const hours = Math.round(minutes / 60);
        if (hours < 24) return toFa(hours) + ' ساعت پیش';
        const days = Math.round(hours / 24);
        if (days < 30) return toFa(days) + ' روز پیش';
        try {
            return new Intl.DateTimeFormat('fa-IR', { day: 'numeric', month: 'long' }).format(then);
        } catch (error) {
            return '';
        }
    }

    /* آیکون‌های تک‌رنگ هم‌خوان با پالت سایت (به‌جای ایموجی رنگی). */
    const ICONS = {
        request_new:
            '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
            '<path d="M5 4h9a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3V4Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>' +
            '<path d="M17 7h2v13H8" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>',
        request_status:
            '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
            '<path d="M20 12a8 8 0 1 1-3.2-6.4L20 4v5h-5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        due_soon:
            '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
            '<circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.7"/>' +
            '<path d="M12 8v4.4l2.6 1.6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
        review:
            '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
            '<path d="m12 4 2.4 5 5.6.8-4 3.9 1 5.5-5-2.6-5 2.6 1-5.5-4-3.9 5.6-.8L12 4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
    };

    /* ---------- نام کاربر در هدر ----------
       صفحه‌هایی که خودشان این کار را می‌کنند (index، books، صفحه‌ی کتابِ ساخته‌شده و…)
       متن دکمه را از قبل عوض کرده‌اند؛ پس اگر هنوز «ورود» است، یعنی این صفحه
       (مثل صفحه‌های نمونه‌ی book1 تا book10) خودش کاری نکرده و ما انجامش می‌دهیم. */
    const DEFAULT_LOGIN_LABEL = 'ورود';

    function paintHeaderIdentity(me) {
        const loginBtn = document.querySelector('.nav-actions .btn-login');
        if (!loginBtn) return;
        if (loginBtn.textContent.trim() !== DEFAULT_LOGIN_LABEL) return;

        loginBtn.textContent = me.name || 'حساب من';
        loginBtn.href = '/panel.html';

        if (me.pendingRequests) {
            const badge = document.createElement('span');
            badge.className = 'nav-user-badge';
            badge.textContent = toFa(me.pendingRequests);
            loginBtn.appendChild(badge);
        }
    }

    function build() {
        const navActions = document.querySelector('.nav-actions');
        if (!navActions || navActions.querySelector('.notif-wrap')) return null;

        const wrap = document.createElement('div');
        wrap.className = 'notif-wrap';

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'notif-btn';
        button.setAttribute('aria-label', 'اعلان‌ها');
        button.setAttribute('aria-expanded', 'false');
        button.innerHTML =
            '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
            '<path d="M18 16v-5a6 6 0 1 0-12 0v5l-2 2h16l-2-2Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>' +
            '<path d="M10 20a2 2 0 0 0 4 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>' +
            '</svg>';

        const badge = document.createElement('span');
        badge.className = 'notif-badge';
        badge.hidden = true;

        const panel = document.createElement('div');
        panel.className = 'notif-panel';
        panel.hidden = true;

        const head = document.createElement('div');
        head.className = 'notif-head';
        const headTitle = document.createElement('strong');
        headTitle.textContent = 'اعلان‌ها';
        const markAll = document.createElement('button');
        markAll.type = 'button';
        markAll.className = 'notif-mark-all';
        markAll.textContent = 'همه خوانده شد';
        head.append(headTitle, markAll);

        const list = document.createElement('div');
        list.className = 'notif-list';

        panel.append(head, list);
        button.appendChild(badge);
        wrap.append(button, panel);
        navActions.insertBefore(wrap, navActions.firstChild);

        return { wrap, button, badge, panel, list, markAll };
    }

    function renderList(ui, items) {
        ui.list.textContent = '';

        if (!items.length) {
            const empty = document.createElement('p');
            empty.className = 'notif-empty';
            empty.textContent = 'اعلان تازه‌ای نداری.';
            ui.list.appendChild(empty);
            return;
        }

        items.forEach((item) => {
            const row = document.createElement(item.link ? 'a' : 'div');
            row.className = 'notif-item' + (item.isRead ? '' : ' unread');
            if (item.link) row.href = item.link;

            const icon = document.createElement('span');
            icon.className = 'notif-icon notif-icon--' + (item.type || 'default');
            icon.innerHTML = ICONS[item.type] || ICONS.request_status;

            const body = document.createElement('div');
            body.className = 'notif-body';

            const title = document.createElement('strong');
            title.textContent = item.title;

            const text = document.createElement('span');
            text.textContent = item.body || '';

            const time = document.createElement('small');
            time.textContent = relativeTime(item.createdAt);

            body.append(title, text, time);
            row.append(icon, body);

            row.addEventListener('click', () => {
                if (!item.isRead) {
                    fetch('/api/notifications/read', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ id: item.id }),
                    }).catch(() => { /* بی‌صدا */ });
                    row.classList.remove('unread');
                }
            });

            ui.list.appendChild(row);
        });
    }

    function updateBadge(ui, unread) {
        ui.badge.textContent = toFa(unread);
        ui.badge.hidden = !unread;
        ui.button.classList.toggle('has-unread', Boolean(unread));
    }

    async function load(ui) {
        try {
            const res = await fetch('/api/notifications');
            if (!res.ok) return;
            const data = await res.json();
            renderList(ui, data.items || []);
            updateBadge(ui, data.unread || 0);
        } catch (error) {
            /* سرور در دسترس نیست؛ زنگ بی‌صدا می‌ماند */
        }
    }

    async function start() {
        ensureStyles();

        let me;
        try {
            me = await (await fetch('/api/me')).json();
        } catch (error) {
            return;
        }
        if (!me || !me.loggedIn) return;

        paintHeaderIdentity(me);

        const ui = build();
        if (!ui) return;

        ui.button.addEventListener('click', (event) => {
            event.stopPropagation();
            const open = ui.panel.hidden;
            ui.panel.hidden = !open;
            ui.button.setAttribute('aria-expanded', String(open));
            if (open) load(ui);
        });

        ui.markAll.addEventListener('click', async () => {
            try {
                await fetch('/api/notifications/read', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                });
                updateBadge(ui, 0);
                load(ui);
            } catch (error) { /* بی‌صدا */ }
        });

        document.addEventListener('click', (event) => {
            if (!ui.wrap.contains(event.target)) {
                ui.panel.hidden = true;
                ui.button.setAttribute('aria-expanded', 'false');
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                ui.panel.hidden = true;
                ui.button.setAttribute('aria-expanded', 'false');
            }
        });

        await load(ui);
        setInterval(() => load(ui), POLL_MS);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
