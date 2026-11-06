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

        /* ---------- کلیک‌پذیر کردن کل باکس کتاب‌ها ----------
           هر .book-card به‌ترتیبِ ظاهرشدن در صفحه، داخل یک <a> پیچیده می‌شود
           و href آن به‌صورت خودکار book1.html، book2.html، ... تنظیم می‌شود.
           این شماره‌گذاری فقط یک‌بار و بر اساس ترتیبِ اصلیِ کتاب‌ها در HTML
           انجام می‌شود، بنابراین با فیلتر کردن یا جست‌وجو تغییر نمی‌کند. */
        const bookCards = Array.from(document.querySelectorAll('#book-grid .book-card'));

        bookCards.forEach((card, index) => {
            const bookNumber = index + 1;
            const bookLink = document.createElement('a');
            bookLink.href = `books/book${bookNumber}.html`;
            bookLink.className = 'book-card-link';
            card.parentNode.insertBefore(bookLink, card);
            bookLink.appendChild(card);
        });

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

        let bookLinks = Array.from(document.querySelectorAll('#book-grid .book-card-link'));

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
            info.appendChild(detailsEl);

            card.appendChild(coverPh);
            card.appendChild(info);
            link.appendChild(card);
            return link;
        }

        async function loadServerBooks() {
            try {
                const res = await fetch('/api/books?per_page=100');
                if (!res.ok) return;
                const books = await res.json();

                books.forEach(book => {
                    const cardEl = buildServerBookCard(book);
                    bookGrid.appendChild(cardEl);
                });

                bookLinks = Array.from(document.querySelectorAll('#book-grid .book-card-link'));
                applyFilters();
            } catch (err) {
                /* بک‌اند در دسترس نیست؛ فقط کتاب‌های نمونه نمایش داده می‌شوند */
            }
        }

        loadServerBooks();
