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

        /* همه‌ی کارت‌های کتاب از /api/books ساخته می‌شوند (کتاب‌های نمونه هم در
           دیتابیس ثبت شده‌اند)، بنابراین اینجا کارتی برای پیچیدن در <a> نیست. */

        /* ---------- جست‌وجو و فیلترِ واقعیِ کتاب‌ها ---------- */
        const searchInput = document.getElementById('search-input');
        const genreFilter = document.getElementById('genre-filter');
        const typeFilter = document.getElementById('type-filter');
        const resetButton = document.getElementById('filter-reset');
        const resultsMeta = document.getElementById('results-meta');
        const emptyState = document.getElementById('empty-state');

        /* اگر کاربر واردشده، دکمه‌ی «ورود» بالای صفحه رو به اسم خودش تغییر بده */
        fetch('/api/me').then(r => r.json()).then(me => {
            if (me.loggedIn) {
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
            }
        });

        let bookLinks = [];
        let booksLoaded = false;

        function applyFilters() {
            const query = searchInput.value.trim().toLowerCase();
            const genre = genreFilter.value;
            const type = typeFilter.value;

            let visibleCount = 0;

            bookLinks.forEach(link => {
                const card = link.querySelector('.book-card');
                const title = (card.dataset.title || '').toLowerCase();
                const author = (card.dataset.author || '').toLowerCase();
                const cardGenre = card.dataset.genre || '';
                const cardType = card.dataset.type || '';

                const matchesQuery = !query || title.includes(query) || author.includes(query);
                const matchesGenre = genre === 'all' || cardGenre === genre;
                const matchesType = type === 'all' || cardType === type;

                const isMatch = matchesQuery && matchesGenre && matchesType;
                link.classList.toggle('hidden', !isMatch);

                if (isMatch) visibleCount++;
            });

            if (!booksLoaded) return;

            resultsMeta.innerHTML = visibleCount > 0
                ? `<strong>${visibleCount}</strong> کتاب پیدا شد`
                : '';
            emptyState.classList.toggle('visible', visibleCount === 0);
        }

        searchInput.addEventListener('input', applyFilters);
        genreFilter.addEventListener('change', applyFilters);
        typeFilter.addEventListener('change', applyFilters);

        resetButton.addEventListener('click', () => {
            searchInput.value = '';
            genreFilter.value = 'all';
            typeFilter.value = 'all';
            applyFilters();
        });

        applyFilters();

        /* ---------- کتاب‌های واقعیِ ثبت‌شده توسط کاربران (از بک‌اند) ----------
           این کتاب‌ها علاوه بر کتاب‌های نمونه‌ی بالا نمایش داده می‌شوند.
           هر کاربر فقط دکمه‌ی حذف را روی کتاب‌های خودش می‌بیند. */
        const shareTypeLabels = { free: 'امانت رایگان', deposit: 'امانت با ودیعه', sale: 'فروش' };
        const bookGrid = document.getElementById('book-grid');

        function buildServerBookCard(book) {
            const link = document.createElement('a');
            link.className = 'book-card-link';
            link.href = book.detailUrl;

            const card = document.createElement('div');
            card.className = 'book-card';
            card.dataset.title = book.title;
            card.dataset.author = book.author;
            card.dataset.genre = book.genre;
            card.dataset.type = book.shareType;
            card.dataset.bookId = book.id;

            const coverPh = document.createElement('div');
            coverPh.className = 'cover-ph';

            const badge = document.createElement('span');
            badge.className = 'badge ' + book.shareType;
            badge.textContent = shareTypeLabels[book.shareType] || book.shareType;
            coverPh.appendChild(badge);

            /* قلبِ علاقه‌مندی: با کلیک روی کارت، صفحه‌ی کتاب باز نشود. */
            const favBtn = document.createElement('button');
            favBtn.type = 'button';
            favBtn.className = 'fav-toggle' + (book.isFavorite ? ' active' : '');
            favBtn.dataset.bookId = book.id;
            favBtn.setAttribute('aria-pressed', String(Boolean(book.isFavorite)));
            favBtn.setAttribute('aria-label', 'ذخیره در علاقه‌مندی‌ها');
            favBtn.innerHTML =
                '<svg viewBox="0 0 24 24" aria-hidden="true">' +
                '<path class="heart-shape" d="M12 21.2c-.32 0-.63-.1-.9-.29C9.9 20 3.6 15.4 3.6 10.2 3.6 7.4 5.8 5.2 8.5 5.2c1.4 0 2.7.62 3.5 1.7.8-1.08 2.1-1.7 3.5-1.7 2.7 0 4.9 2.2 4.9 5 0 5.2-6.3 9.8-7.5 10.71-.27.19-.58.29-.9.29Z" />' +
                '</svg>';
            favBtn.addEventListener('click', async (event) => {
                event.preventDefault();
                event.stopPropagation();

                const res = await fetch(`/api/books/${book.id}/favorite`, { method: 'POST' });
                const data = await res.json().catch(() => ({}));
                if (res.status === 401) {
                    location.href = '/login.html';
                    return;
                }
                if (!res.ok) return;
                favBtn.classList.toggle('active', Boolean(data.favorited));
                favBtn.setAttribute('aria-pressed', String(Boolean(data.favorited)));
            });
            coverPh.appendChild(favBtn);

            if (book.cover) {
                const img = document.createElement('img');
                img.src = book.cover;
                img.alt = book.title;
                img.className = 'cover-book';
                img.onerror = () => img.remove();
                coverPh.appendChild(img);
            }

            /* اطلاعات کتاب از کاربر می‌آید؛ با textContent ساخته می‌شود تا HTML داخل
               عنوان/نویسنده/آدرس اجرا نشود (جلوگیری از XSS ذخیره‌شده). */
            const info = document.createElement('div');
            info.className = 'book-info';

            const titleEl = document.createElement('h4');
            titleEl.textContent = book.title;

            const authorEl = document.createElement('p');
            authorEl.className = 'author';
            authorEl.textContent = book.author;

            const locEl = document.createElement('p');
            locEl.className = 'loc';
            locEl.textContent = '📍 ' + (book.address || '');

            const detailsEl = document.createElement('span');
            detailsEl.className = 'details-link';
            detailsEl.textContent = 'جزئیات ←';

            info.appendChild(titleEl);
            info.appendChild(authorEl);
            info.appendChild(locEl);

            if (book.ratingCount) {
                const ratingEl = document.createElement('p');
                ratingEl.className = 'rating-line';

                const stars = document.createElement('span');
                stars.className = 'rating-stars';
                const rounded = Math.round(book.ratingAvg);
                for (let i = 1; i <= 5; i += 1) {
                    const star = document.createElement('span');
                    star.className = i <= rounded ? 'on' : 'off';
                    star.textContent = '★';
                    stars.appendChild(star);
                }

                const fa = (v) => String(v).replace(/[0-9]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
                const caption = document.createElement('span');
                caption.textContent = ' ' + fa(book.ratingAvg) + ' (' + fa(book.ratingCount) + ')';

                ratingEl.append(stars, caption);
                info.appendChild(ratingEl);
            }

            info.appendChild(detailsEl);

            card.appendChild(coverPh);
            card.appendChild(info);
            link.appendChild(card);
            return link;
        }

        async function loadServerBooks() {
            const loading = document.getElementById('books-loading');
            try {
                const res = await fetch('/api/books?per_page=100');
                if (!res.ok) throw new Error('bad response');
                const books = await res.json();

                if (loading) loading.remove();

                books.forEach(book => {
                    const cardEl = buildServerBookCard(book);
                    bookGrid.appendChild(cardEl);
                });

                bookLinks = Array.from(document.querySelectorAll('#book-grid .book-card-link'));
                booksLoaded = true;
                applyFilters();
            } catch (err) {
                if (loading) {
                    loading.textContent = 'بارگذاری کتاب‌ها انجام نشد. مطمئن شو سرور در حال اجراست و صفحه را دوباره باز کن.';
                }
            }
        }

        loadServerBooks();
