/* =========================================================
   صفحه‌ی اختصاصی کتاب — کتاب‌به‌کتاب
   - نمایش نام کاربر در هدر
   - دکمه‌ی حذف برای صاحب کتاب
   - ثبت واقعی درخواست امانت/خرید
========================================================= */
(function () {
    'use strict';

    const el = (id) => document.getElementById(id);
    const toFa = (v) => String(v).replace(/[0-9]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
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

    /* ---------- علاقه‌مندی‌ها (قلب روی جلد + دکمه‌ی کارت درخواست) ---------- */
    const favBtn = el('fav-btn');
    const heroFav = el('hero-fav');
    const favText = el('fav-btn-text');
    const favBookId = (favBtn && favBtn.dataset.bookId) || (heroFav && heroFav.dataset.bookId) || '';

    function paintFavorite(favorited) {
        if (favBtn) {
            favBtn.classList.toggle('active', favorited);
            favBtn.setAttribute('aria-pressed', String(favorited));
        }
        if (favText) favText.textContent = favorited ? 'ذخیره شده در علاقه‌مندی‌ها' : 'ذخیره در علاقه‌مندی‌ها';
        if (heroFav) {
            heroFav.classList.toggle('active', favorited);
            heroFav.setAttribute('aria-pressed', String(favorited));
            heroFav.setAttribute(
                'title',
                favorited ? 'از علاقه‌مندی‌ها بردار' : 'ذخیره در علاقه‌مندی‌ها',
            );
        }
    }

    async function toggleFavorite(trigger) {
        if (!currentUser || !currentUser.loggedIn) {
            location.href = '/login.html';
            return;
        }
        if (trigger) trigger.disabled = true;
        try {
            const res = await fetch(`/api/books/${favBookId}/favorite`, { method: 'POST' });
            const data = await res.json().catch(() => ({}));
            if (res.status === 401) {
                location.href = '/login.html';
                return;
            }
            if (!res.ok) {
                alert(data.error || 'ذخیره‌ی علاقه‌مندی انجام نشد.');
                return;
            }
            paintFavorite(Boolean(data.favorited));
        } catch (error) {
            alert('اتصال به سرور برقرار نشد.');
        } finally {
            if (trigger) trigger.disabled = false;
        }
    }

    if (favBookId && (favBtn || heroFav)) {
        fetch(`/api/books/${favBookId}/favorite`)
            .then((res) => res.json())
            .then((data) => paintFavorite(Boolean(data.favorited)))
            .catch(() => { /* بی‌صدا */ });

        [favBtn, heroFav].forEach((button) => {
            if (button) button.addEventListener('click', () => toggleFavorite(button));
        });
    }

    /* ---------- امتیاز و نظر ---------- */
    const reviewsSection = el('reviews-section');
    const reviewsList = el('reviews-list');
    const reviewsSummary = el('reviews-summary');
    const reviewForm = el('review-form');
    const reviewFormTitle = el('review-form-title');
    const reviewComment = el('review-comment');
    const reviewNote = el('review-note');
    const reviewsLocked = el('reviews-locked');
    const starPicker = el('star-picker');

    let selectedRating = 0;

    /* ستاره‌ها با span ساخته می‌شوند تا پُر و خالی از هم قابل تشخیص باشد. */
    function starsNode(rating) {
        const box = document.createElement('span');
        box.className = 'review-stars';
        for (let i = 1; i <= 5; i += 1) {
            const star = document.createElement('span');
            star.className = i <= rating ? 'on' : 'off';
            star.textContent = '★';
            box.appendChild(star);
        }
        return box;
    }

    function faDate(value) {
        if (!value) return '';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '';
        try {
            return new Intl.DateTimeFormat('fa-IR', { day: 'numeric', month: 'long', year: 'numeric' }).format(date);
        } catch (error) {
            return '';
        }
    }

    function setRating(value) {
        selectedRating = value;
        if (!starPicker) return;
        Array.from(starPicker.querySelectorAll('.star')).forEach((star) => {
            star.classList.toggle('on', Number(star.dataset.value) <= value);
        });
    }

    if (starPicker) {
        starPicker.addEventListener('click', (event) => {
            const star = event.target.closest('.star');
            if (star) setRating(Number(star.dataset.value));
        });
    }

    function renderReviews(data) {
        const items = data.reviews || [];

        // امتیاز خلاصه در هدر صفحه
        const heroRating = el('hero-rating');
        if (heroRating) {
            if (data.count) {
                heroRating.hidden = false;
                heroRating.textContent = '★ ' + toFa(data.average) + ' از ۵ · ' + toFa(data.count) + ' نظر';
            } else {
                heroRating.hidden = true;
            }
        }

        if (reviewsSummary) {
            reviewsSummary.textContent = '';
            if (data.count) {
                reviewsSummary.appendChild(starsNode(Math.round(data.average)));
                const caption = document.createElement('span');
                caption.className = 'reviews-summary-text';
                caption.textContent = ` ${toFa(data.average)} از ۵ · ${toFa(data.count)} نظر`;
                reviewsSummary.appendChild(caption);
            } else {
                reviewsSummary.textContent = 'هنوز امتیازی ثبت نشده است';
            }
        }

        if (reviewsList) {
            reviewsList.textContent = '';
            items.forEach((review) => {
                const card = document.createElement('article');
                card.className = 'review-card';

                const head = document.createElement('div');
                head.className = 'review-card-head';

                const name = document.createElement('strong');
                name.textContent = review.userName || 'کاربر';

                head.append(name, starsNode(review.rating));

                const meta = document.createElement('small');
                meta.textContent = faDate(review.createdAt) + (review.isMine ? ' · نظر تو' : '');

                card.append(head, meta);

                if (review.comment) {
                    const text = document.createElement('p');
                    text.textContent = review.comment;
                    card.appendChild(text);
                }

                if (review.isMine) {
                    const remove = document.createElement('button');
                    remove.type = 'button';
                    remove.className = 'review-delete';
                    remove.textContent = 'حذف نظر من';
                    remove.addEventListener('click', async () => {
                        if (!confirm('نظرت حذف شود؟')) return;
                        const res = await fetch(`/api/books/${reviewsSection.dataset.bookId}/reviews`, {
                            method: 'DELETE',
                        });
                        if (res.ok) loadReviews();
                    });
                    card.appendChild(remove);
                }

                reviewsList.appendChild(card);
            });
        }

        // فرم فقط برای کسانی که امانت/خریدشان کامل شده باز می‌شود.
        if (reviewForm) {
            reviewForm.hidden = !data.canReview;
            if (data.canReview) {
                if (reviewFormTitle) {
                    reviewFormTitle.textContent = data.myReview ? 'نظرت را ویرایش کن' : 'نظرت را ثبت کن';
                }
                if (data.myReview) {
                    setRating(data.myReview.rating);
                    if (reviewComment) reviewComment.value = data.myReview.comment || '';
                }
            }
        }
        if (reviewsLocked) {
            reviewsLocked.hidden = Boolean(data.canReview);
        }
    }

    async function loadReviews() {
        if (!reviewsSection) return;
        const bookId = reviewsSection.dataset.bookId;
        try {
            const res = await fetch(`/api/books/${bookId}/reviews`);
            if (!res.ok) return;
            renderReviews(await res.json());
        } catch (error) {
            /* بی‌صدا */
        }
    }

    if (reviewForm && reviewsSection) {
        reviewForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            if (!selectedRating) {
                if (reviewNote) {
                    reviewNote.className = 'review-note bad';
                    reviewNote.textContent = 'اول امتیازت را با ستاره‌ها انتخاب کن.';
                }
                return;
            }

            const submit = reviewForm.querySelector('.review-submit');
            submit.disabled = true;
            if (reviewNote) {
                reviewNote.className = 'review-note';
                reviewNote.textContent = 'در حال ثبت…';
            }

            try {
                const res = await fetch(`/api/books/${reviewsSection.dataset.bookId}/reviews`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ rating: selectedRating, comment: reviewComment.value.trim() }),
                });
                const data = await res.json().catch(() => ({}));

                if (!res.ok) {
                    if (reviewNote) {
                        reviewNote.className = 'review-note bad';
                        reviewNote.textContent = data.error || 'ثبت نظر انجام نشد.';
                    }
                    return;
                }

                if (reviewNote) {
                    reviewNote.className = 'review-note ok';
                    reviewNote.textContent = 'نظرت ثبت شد. ممنون!';
                }
                loadReviews();
            } catch (error) {
                if (reviewNote) {
                    reviewNote.className = 'review-note bad';
                    reviewNote.textContent = 'اتصال به سرور برقرار نشد.';
                }
            } finally {
                submit.disabled = false;
            }
        });
    }

    /* ---------- کتاب‌های مشابه ---------- */
    const similarBlock = el('similar-block');
    const similarList = el('similar-list');

    function similarItem(book) {
        const link = document.createElement('a');
        link.className = 'similar-item';
        link.href = book.detailUrl || '/books.html';

        const cover = document.createElement('span');
        cover.className = 'similar-cover';
        if (book.cover) {
            const img = document.createElement('img');
            img.src = book.cover;
            img.alt = '';
            img.loading = 'lazy';
            img.addEventListener('error', () => img.remove());
            cover.appendChild(img);
        } else {
            cover.textContent = (book.title || '?').trim().charAt(0);
        }

        const info = document.createElement('span');
        info.className = 'similar-info';

        const title = document.createElement('strong');
        title.textContent = book.title;

        const meta = document.createElement('span');
        const parts = [book.author];
        if (book.ratingCount) parts.push('★ ' + toFa(book.ratingAvg));
        meta.textContent = parts.filter(Boolean).join(' · ');

        info.append(title, meta);
        link.append(cover, info);
        return link;
    }

    async function loadSimilarBooks() {
        if (!similarBlock || !similarList) return;
        const genre = similarBlock.dataset.genre;
        const currentId = Number(similarBlock.dataset.bookId);
        try {
            const res = await fetch('/api/books?per_page=100');
            if (!res.ok) return;
            const books = await res.json();
            const pool = books.filter((book) => book.id !== currentId);
            const sameGenre = pool.filter((book) => book.genre === genre);
            const others = pool.filter((book) => book.genre !== genre);
            const picked = sameGenre.concat(others).slice(0, 6);
            if (!picked.length) return;

            similarList.textContent = '';
            picked.forEach((book) => similarList.appendChild(similarItem(book)));
            similarBlock.hidden = false;
        } catch (error) {
            /* بی‌صدا: اگر API در دسترس نبود، این بخش نمایش داده نمی‌شود */
        }
    }

    loadReviews();
    loadSimilarBooks();
})();
