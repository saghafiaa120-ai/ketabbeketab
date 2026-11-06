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

        /* ---------- Upload Page: عناصر مورد نیاز ---------- */
        const titleInput = document.getElementById('title');
        const authorInput = document.getElementById('author');
        const addressInput = document.getElementById('address');
        const shareTypeInputs = document.querySelectorAll('input[name="share-type"]');
        const durationField = document.getElementById('field-duration');
        const depositField = document.getElementById('field-deposit');
        const priceField = document.getElementById('field-price');

        /* ---------- تغییر فیلدهای شرطی بر اساس نوع اشتراک‌گذاری ---------- */
        function updateConditionalFields() {
            const selectedType = document.querySelector('input[name="share-type"]:checked')?.value || 'free';

            depositField.classList.toggle('visible', selectedType === 'deposit');
            priceField.classList.toggle('visible', selectedType === 'sale');
            durationField.style.display = (selectedType === 'sale') ? 'none' : 'block';
        }

        shareTypeInputs.forEach(input => {
            input.addEventListener('change', updateConditionalFields);
        });

        updateConditionalFields();

        /* ---------- آپلود و پیش‌نمایش تصویر جلد کتاب (فقط سمت کاربر) ---------- */
        const dropzone = document.getElementById('cover-dropzone');
        const fileInput = document.getElementById('cover-input');
        const coverThumb = document.getElementById('cover-thumb');

        function handleCoverFile(file) {
            if (!file || !file.type.startsWith('image/')) return;
            const reader = new FileReader();
            reader.onload = (event) => {
                coverThumb.src = event.target.result;
                dropzone.classList.add('has-image');
            };
            reader.readAsDataURL(file);
        }

        dropzone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', () => handleCoverFile(fileInput.files[0]));

        dropzone.addEventListener('dragover', (event) => {
            event.preventDefault();
            dropzone.classList.add('dragover');
        });
        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
        dropzone.addEventListener('drop', (event) => {
            event.preventDefault();
            dropzone.classList.remove('dragover');
            handleCoverFile(event.dataTransfer.files[0]);
        });

        /* ---------- بررسی ورود کاربر؛ بدون ورود اجازه‌ی آپلود نیست ----------
           یک درخواست کافی است: هم نام کاربر در نوار بالا ست می‌شود، هم گارد ورود. */
        fetch('/api/me').then(r => r.json()).then(me => {
            if (!me.loggedIn) {
                window.location.href = 'login.html';
                return;
            }
            const loginBtn = document.querySelector('.nav-actions .btn-login');
            if (loginBtn) { loginBtn.textContent = me.name; loginBtn.href = '/panel.html'; }
        });

        /* ---------- اعتبارسنجی و ارسالِ واقعیِ فرم به بک‌اند ---------- */
        const uploadForm = document.getElementById('upload-form');
        const formSuccess = document.getElementById('form-success');
        const submitBtn = uploadForm.querySelector('.submit-btn');

        function setFieldState(fieldId, isValid) {
            const field = document.getElementById(fieldId);
            field.classList.toggle('error', !isValid);
            field.classList.toggle('success', isValid);
        }

        uploadForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const selectedType = document.querySelector('input[name="share-type"]:checked')?.value || 'free';

            const checks = {
                'field-title': titleInput.value.trim().length > 1,
                'field-author': authorInput.value.trim().length > 1,
                'field-genre': document.getElementById('genre').value !== '',
                'field-condition': document.getElementById('condition').value !== '',
                'field-address': addressInput.value.trim().length > 4
            };

            if (selectedType === 'deposit') {
                checks['field-deposit'] = Number(document.getElementById('deposit-amount').value) > 0;
            }
            if (selectedType === 'sale') {
                checks['field-price'] = Number(document.getElementById('sale-price').value) > 0;
            }

            Object.entries(checks).forEach(([fieldId, isValid]) => setFieldState(fieldId, isValid));

            const allValid = Object.values(checks).every(Boolean);

            if (!allValid) {
                formSuccess.classList.remove('visible');
                return;
            }

            const payload = new FormData();
            payload.append('title', titleInput.value.trim());
            payload.append('author', authorInput.value.trim());
            payload.append('genre', document.getElementById('genre').value);
            payload.append('condition', document.getElementById('condition').value);
            payload.append('shareType', selectedType);
            payload.append('duration', document.getElementById('duration').value || '');
            payload.append('depositAmount', document.getElementById('deposit-amount').value || '');
            payload.append('salePrice', document.getElementById('sale-price').value || '');
            payload.append('address', addressInput.value.trim());
            payload.append('description', document.getElementById('description').value.trim());
            if (fileInput.files[0]) {
                payload.append('cover', fileInput.files[0]);
            }

            submitBtn.disabled = true;

            try {
                const res = await fetch('/api/books', { method: 'POST', body: payload });
                const data = await res.json();

                if (!res.ok) {
                    alert(data.error || 'خطایی رخ داد. دوباره تلاش کن.');
                    submitBtn.disabled = false;
                    return;
                }

                formSuccess.classList.add('visible');
                uploadForm.reset();
                dropzone.classList.remove('has-image');
                coverThumb.src = '';
                Object.keys(checks).forEach(fieldId => {
                    document.getElementById(fieldId).classList.remove('success', 'error');
                });
                updateConditionalFields();
            } catch (err) {
                alert('اتصال به سرور برقرار نشد. مطمئن شو Flask در حال اجراست.');
            } finally {
                submitBtn.disabled = false;
            }
        });
