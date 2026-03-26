/* ===== ELEMENT REFERENCES ===== */
const form        = document.getElementById('recipeForm');
const submitBtn   = document.getElementById('submitBtn');
const btnText     = document.getElementById('btnText');
const btnIcon     = document.getElementById('btnIcon');
const loadingEl   = document.getElementById('loadingState');
const errorBanner = document.getElementById('errorBanner');
const errorMsg    = document.getElementById('errorMessage');
const resultCard  = document.getElementById('resultCard');

/* ===== FORM SUBMIT ===== */
form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const ingredients = document.getElementById('ingredients').value.trim();
  const diet        = document.getElementById('diet').value;
  const allergies   = document.getElementById('allergies').value.trim();

  // Validate bắt buộc nguyên liệu
  const errEl = document.getElementById('ingredientsError');
  if (!ingredients) {
    errEl.classList.remove('hidden');
    document.getElementById('ingredients').focus();
    return;
  }
  errEl.classList.add('hidden');

  setLoading(true);
  hideError();
  hideResult();

  try {
    const res = await fetch('http://localhost:5000/api/generate_recipe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ingredients, diet, allergies }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error || `Server trả về lỗi ${res.status}`);
    }

    const data = await res.json();
    if (data.error) throw new Error(data.error);

    renderResult(data);
  } catch (err) {
    showError(
      err.message ||
      'Không thể kết nối đến server. Hãy đảm bảo backend đang chạy trên cổng 5000.'
    );
  } finally {
    setLoading(false);
  }
});

/* ===== UI HELPERS ===== */

function setLoading(on) {
  submitBtn.disabled = on;
  loadingEl.classList.toggle('hidden', !on);
  if (on) {
    btnIcon.textContent = '';
    btnText.textContent = 'Đang xử lý...';
  } else {
    btnIcon.textContent = '🍽️';
    btnText.textContent = 'Tạo thực đơn ngay';
  }
}

function showError(msg) {
  errorMsg.textContent = msg;
  errorBanner.classList.remove('hidden');
}

function hideError() {
  errorBanner.classList.add('hidden');
}

function hideResult() {
  resultCard.classList.add('hidden');
  resultCard.classList.remove('animate-slide-up');
}

/* ===== RENDER RESULT ===== */

function renderResult(data) {
  document.getElementById('dishName').textContent =
    data.dish_name || 'Món ngon không tên 🍜';
  document.getElementById('calories').textContent =
    data.calories || 'Chưa xác định';

  const steps = (data.recipe || '').split('\n').filter(l => l.trim());
  const ol = document.getElementById('recipeSteps');
  ol.innerHTML = '';

  steps.forEach((step, i) => {
    const cleanStep = step.replace(/^\d+\.\s*/, '').trim();
    if (!cleanStep) return;

    const li = document.createElement('li');
    li.className = 'flex gap-3 items-start';
    li.innerHTML = `
      <span class="step-badge flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-violet-300 mt-0.5">
        ${i + 1}
      </span>
      <p class="text-sm text-slate-300 leading-relaxed">${cleanStep}</p>
    `;
    ol.appendChild(li);
  });

  resultCard.classList.remove('hidden');
  void resultCard.offsetWidth; // force reflow để restart animation
  resultCard.classList.add('animate-slide-up');
  resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ===== RESET FORM ===== */

function resetForm() {
  form.reset();
  hideResult();
  hideError();
  window.scrollTo({ top: 0, behavior: 'smooth' });
  document.getElementById('ingredients').focus();
}
