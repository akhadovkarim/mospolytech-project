const API = '/api';

const $ = (id) => document.getElementById(id);

const STRENGTH_LABELS = { weak: 'Слабый', medium: 'Средний', strong: 'Надёжный' };

// ---------- Утилиты ----------

async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  let data = null;
  try { data = await res.json(); } catch (_) { /* пустой ответ */ }
  if (!res.ok) {
    const msg = (data && data.detail) ? data.detail : `Ошибка ${res.status}`;
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

let toastTimer = null;
function toast(message, isError = false) {
  const el = $('toast');
  el.textContent = message;
  el.className = 'toast' + (isError ? ' toast--error' : '');
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2600);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
  toast('Скопировано в буфер обмена');
}

function setBusy(btn, busy) {
  btn.disabled = busy;
  if (busy) {
    btn.dataset.label = btn.textContent;
    btn.textContent = 'Подождите…';
  } else if (btn.dataset.label) {
    btn.textContent = btn.dataset.label;
  }
}

// ---------- Состояние сервера ----------

async function checkHealth() {
  const el = $('health');
  const text = el.querySelector('.status__text');
  try {
    const data = await api('/health');
    el.className = 'status status--ok';
    text.textContent = `API: ok · БД: ${data.database === 'connected' ? 'подключена' : data.database}`;
  } catch (e) {
    el.className = 'status status--error';
    text.textContent = 'API недоступен';
  }
}

// ---------- Генератор паролей ----------

const pwLength = $('pw-length');
const pwLengthValue = $('pw-length-value');
pwLength.addEventListener('input', () => { pwLengthValue.textContent = pwLength.value; });

$('pw-generate').addEventListener('click', async () => {
  const btn = $('pw-generate');
  const body = {
    length: Number(pwLength.value),
    upper: $('pw-upper').checked,
    lower: $('pw-lower').checked,
    digits: $('pw-digits').checked,
    symbols: $('pw-symbols').checked,
  };
  if (!body.upper && !body.lower && !body.digits && !body.symbols) {
    toast('Выберите хотя бы один набор символов', true);
    return;
  }
  setBusy(btn, true);
  try {
    const data = await api('/passwords/generate', { method: 'POST', body: JSON.stringify(body) });
    $('pw-output').textContent = data.value;
    const wrap = $('pw-output-wrap');
    wrap.hidden = false;
    const strength = wrap.querySelector('.strength');
    strength.className = `strength strength--${data.strength}`;
    $('pw-strength-label').textContent = `${STRENGTH_LABELS[data.strength] || data.strength} · ${data.entropy_bits} бит`;
  } catch (e) {
    toast(e.message, true);
  } finally {
    setBusy(btn, false);
  }
});

$('pw-copy').addEventListener('click', () => copyText($('pw-output').textContent));

// ---------- Генератор хэшей ----------

$('hash-generate').addEventListener('click', async () => {
  const btn = $('hash-generate');
  const text = $('hash-text').value;
  const algorithm = $('hash-algo').value;
  if (!text.trim()) {
    toast('Введите текст для хэширования', true);
    $('hash-text').focus();
    return;
  }
  setBusy(btn, true);
  try {
    const data = await api('/hashes', { method: 'POST', body: JSON.stringify({ text, algorithm }) });
    $('hash-output').textContent = data.hash_value;
    $('hash-meta').textContent = `${data.algorithm} · ${data.hash_value.length} символов · сохранено #${data.id}`;
    $('hash-output-wrap').hidden = false;
  } catch (e) {
    toast(e.message, true);
  } finally {
    setBusy(btn, false);
  }
});

$('hash-copy').addEventListener('click', () => copyText($('hash-output').textContent));

// ---------- Данные из БД ----------

const results = $('results');

function renderError(message) {
  results.innerHTML = `<div class="error-box">${escapeHtml(message)}</div>`;
}

function renderEmpty(title) {
  results.innerHTML = `<p class="results__title">${escapeHtml(title)}</p><p class="placeholder">Записей нет.</p>`;
}

function flag(v) {
  return v ? '<span class="yes">✓</span>' : '<span class="no">—</span>';
}

function renderPasswords(items) {
  if (!items.length) return renderEmpty('Пароли из БД');
  const rows = items.map((p) => `
    <tr>
      <td class="num">${p.id}</td>
      <td class="mono">${escapeHtml(p.value)}</td>
      <td class="num">${p.length}</td>
      <td>${flag(p.has_upper)}</td>
      <td>${flag(p.has_lower)}</td>
      <td>${flag(p.has_digits)}</td>
      <td>${flag(p.has_symbols)}</td>
      <td><span class="tag tag--${p.strength}">${STRENGTH_LABELS[p.strength] || p.strength}</span></td>
      <td class="nowrap">${formatDate(p.created_at)}</td>
    </tr>`).join('');
  results.innerHTML = `
    <p class="results__title">Пароли из БД <small>последние ${items.length}</small></p>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th class="num">#</th><th>Пароль</th><th class="num">Длина</th>
          <th>A–Z</th><th>a–z</th><th>0–9</th><th>!@#</th><th>Стойкость</th><th>Создан</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function renderHashes(items, algorithm) {
  const title = algorithm ? `Хэши из БД: ${algorithm}` : 'Хэши из БД';
  if (!items.length) return renderEmpty(title);
  const rows = items.map((h) => `
    <tr>
      <td class="num">${h.id}</td>
      <td>${escapeHtml(h.source_text)}</td>
      <td><span class="tag tag--algo">${escapeHtml(h.algorithm)}</span></td>
      <td class="mono">${escapeHtml(h.hash_value)}</td>
      <td class="nowrap">${formatDate(h.created_at)}</td>
    </tr>`).join('');
  results.innerHTML = `
    <p class="results__title">${escapeHtml(title)} <small>последние ${items.length}</small></p>
    <div class="table-wrap">
      <table>
        <thead><tr><th class="num">#</th><th>Текст</th><th>Алгоритм</th><th>Хэш</th><th>Создан</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function renderStats(s) {
  const strengthRows = Object.entries(s.passwords.by_strength).map(([k, v]) => `
    <tr><td><span class="tag tag--${k}">${STRENGTH_LABELS[k] || k}</span></td><td class="num">${v}</td></tr>`).join('');
  const algoRows = Object.entries(s.hashes.by_algorithm).map(([k, v]) => `
    <tr><td><span class="tag tag--algo">${k}</span></td><td class="num">${v}</td></tr>`).join('');
  results.innerHTML = `
    <p class="results__title">Статистика</p>
    <div class="stats">
      <div class="stat-card">
        <h3>Паролей в БД</h3>
        <div class="big">${s.passwords.total}</div>
        <table>
          <tbody>
            ${strengthRows}
            <tr><td>Средняя длина</td><td class="num">${s.passwords.avg_length}</td></tr>
          </tbody>
        </table>
      </div>
      <div class="stat-card">
        <h3>Хэшей в БД</h3>
        <div class="big">${s.hashes.total}</div>
        <table><tbody>${algoRows}</tbody></table>
      </div>
    </div>`;
}

async function loadInto(btn, fn) {
  setBusy(btn, true);
  results.innerHTML = '<p class="placeholder">Загрузка…</p>';
  try {
    await fn();
  } catch (e) {
    renderError(e.message);
  } finally {
    setBusy(btn, false);
  }
}

$('db-passwords').addEventListener('click', () =>
  loadInto($('db-passwords'), async () => {
    const data = await api('/passwords');
    renderPasswords(data.items);
  }));

$('db-hashes').addEventListener('click', () =>
  loadInto($('db-hashes'), async () => {
    const algorithm = $('db-hash-filter').value;
    const query = algorithm ? `?algorithm=${encodeURIComponent(algorithm)}` : '';
    const data = await api('/hashes' + query);
    renderHashes(data.items, algorithm);
  }));

$('db-hash-filter').addEventListener('change', () => $('db-hashes').click());

$('db-stats').addEventListener('click', () =>
  loadInto($('db-stats'), async () => {
    renderStats(await api('/stats'));
  }));

$('db-clear').addEventListener('click', () => {
  if (!confirm('Удалить все сохранённые пароли и хэши? Это действие нельзя отменить.')) return;
  loadInto($('db-clear'), async () => {
    const data = await api('/history', { method: 'DELETE' });
    toast(`Удалено: паролей ${data.deleted.passwords}, хэшей ${data.deleted.hashes}`);
    results.innerHTML = '<p class="placeholder">История очищена. Таблицы пусты.</p>';
  });
});

// ---------- Старт ----------

checkHealth();
setInterval(checkHealth, 15000);
