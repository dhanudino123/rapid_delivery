// Shared: REST client, auth, header/footer, product card
// If a page is opened straight from disk (file://) talk to the local server instead.
const BASE = location.protocol === 'file:' ? 'http://localhost:8000' : '';
const OFFLINE_MSG = 'Cannot reach the Flipcart server. Start it with Open_Flipcart (or run "python app.py") and open http://localhost:8000';

const API = {
  token: () => localStorage.getItem('fc_token'),
  user: () => { try { return JSON.parse(localStorage.getItem('fc_user')); } catch { return null; } },
  setSession(t, u) { localStorage.setItem('fc_token', t); localStorage.setItem('fc_user', JSON.stringify(u)); },
  clear() { localStorage.removeItem('fc_token'); localStorage.removeItem('fc_user'); },
  async request(method, url, body) {
    const headers = { 'Content-Type': 'application/json' };
    if (API.token()) headers.Authorization = 'Bearer ' + API.token();
    let res;
    try { res = await fetch(BASE + url, { method, headers, body: body ? JSON.stringify(body) : undefined }); }
    catch { const e = new Error(OFFLINE_MSG); e.status = 0; throw e; }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 401 && API.token()) API.clear();
      const e = new Error(data.error || 'Something went wrong'); e.status = res.status; throw e;
    }
    return data;
  },
  get: u => API.request('GET', u), post: (u, b) => API.request('POST', u, b || {}),
  patch: (u, b) => API.request('PATCH', u, b), del: u => API.request('DELETE', u),
  // send visitors to login and bring them back afterwards
  requireLogin() {
    if (API.token()) return true;
    location.href = 'login.html?next=' + encodeURIComponent(location.pathname.split('/').pop() + location.search);
    return false;
  }
};

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const rupee = n => '₹' + Number(n).toLocaleString('en-IN');
const dateFmt = s => new Date(s.replace(' ', 'T') + 'Z').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
const dateTimeFmt = s => new Date(s.replace(' ', 'T') + 'Z').toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

function toast(msg) {
  let el = document.getElementById('toast');
  if (!el) { el = document.createElement('div'); el.id = 'toast'; el.className = 'toast'; document.body.appendChild(el); }
  el.textContent = msg; el.classList.add('show');
  clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove('show'), 2400);
}

function rateBadge(r) {
  const cls = r >= 4 ? '' : r >= 3 ? 'mid' : 'low';
  return `<span class="rate ${cls}">${Number(r).toFixed(1)} ★</span>`;
}

function productCard(p) {
  return `<a class="pcard" href="product.html?id=${p.id}">
    <img src="${esc(p.image)}" alt="${esc(p.name)}" loading="lazy">
    <h3>${esc(p.name)}</h3>
    <div class="desc">${esc(p.description)}</div>
    <div>${rateBadge(p.rating)} <span class="muted">(${Number(p.rating_count).toLocaleString('en-IN')})</span></div>
    <div class="price-line"><span class="price">${rupee(p.price)}</span><span class="mrp">${rupee(p.mrp)}</span>${p.discount > 0 ? `<span class="off">${p.discount}% off</span>` : ''}</div>
    ${p.stock === 0 ? '<div class="low-stock">Out of stock</div>' : p.stock <= 10 ? `<div class="low-stock">Only ${p.stock} left</div>` : '<div class="free-del">Free delivery</div>'}
  </a>`;
}

/* ---------- header / footer ---------- */
function buildHeader() {
  const host = document.getElementById('site-header');
  if (host) {
    const q = new URLSearchParams(location.search).get('q') || '';
    host.innerHTML = `<header class="hdr"><div class="hdr-in">
      <a class="logo" href="index.html"><b>Flipcart</b><i>Explore <span>Plus ✦</span></i></a>
      <form class="search" id="search-form" action="index.html" autocomplete="off">
        <input name="q" id="search-input" value="${esc(q)}" placeholder="Search for products, brands and more" aria-label="Search">
        <button aria-label="Search">🔍</button><ul class="suggest" id="suggest" hidden></ul>
      </form>
      <div class="hdr-right"><span id="auth-slot"></span>
        <a class="cart-link" href="cart.html">🛒 Cart <span id="cart-count" class="cart-count">0</span></a></div>
    </div></header>`;
    renderAuth(); setupSuggest();
  }
  const f = document.getElementById('site-footer');
  if (f) f.innerHTML = `<footer class="footer"><div class="wrap"><div><b>🛍️ Flipcart</b> – e-commerce project built with Python (Flask) + SQLite. Product photos: Pexels / Wikimedia Commons.</div>
    <div><a href="index.html">Home</a> · <a href="orders.html">My Orders</a> · <a href="cart.html">Cart</a></div></div></footer>`;
}

function renderAuth() {
  const slot = document.getElementById('auth-slot'); if (!slot) return;
  const u = API.user();
  if (u && API.token()) {
    slot.innerHTML = `<div class="menu"><button>👤 ${esc(u.name.split(' ')[0])} ▾</button><div class="menu-list">
      <a href="orders.html">📦 My Orders</a>${u.is_admin ? '<a href="admin.html">⚙️ Admin Panel</a>' : ''}<a href="#" id="logout-link">⎋ Logout</a></div></div>`;
    document.getElementById('logout-link').addEventListener('click', async e => {
      e.preventDefault(); try { await API.post('/api/auth/logout'); } catch {} API.clear(); location.href = 'index.html';
    });
  } else {
    slot.innerHTML = `<a class="login-btn" href="login.html?next=${encodeURIComponent(location.pathname.split('/').pop() + location.search)}">Login</a>`;
  }
}

function setupSuggest() {
  const input = document.getElementById('search-input'), box = document.getElementById('suggest');
  let t;
  input.addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const q = input.value.trim();
      if (q.length < 2) { box.hidden = true; return; }
      try {
        const s = await API.get('/api/suggest?q=' + encodeURIComponent(q));
        box.innerHTML = s.map(x => x.type === 'category'
          ? `<li data-href="index.html?category=${x.slug}">🔍 ${esc(x.label)} <small>in Categories</small></li>`
          : `<li data-href="index.html?q=${encodeURIComponent(x.label)}">🔍 ${esc(x.label)}</li>`).join('');
        box.hidden = !s.length;
      } catch { box.hidden = true; }
    }, 180);
  });
  box.addEventListener('mousedown', e => { const li = e.target.closest('li'); if (li) location.href = li.dataset.href; });
  input.addEventListener('blur', () => setTimeout(() => (box.hidden = true), 150));
}

async function refreshCartCount() {
  const el = document.getElementById('cart-count'); if (!el) return;
  if (!API.token()) { el.textContent = '0'; return; }
  try { el.textContent = (await API.get('/api/cart')).count; } catch { el.textContent = '0'; }
}

// product image missing/blocked -> show a neutral placeholder instead of a broken icon
const PLACEHOLDER = 'data:image/svg+xml;utf8,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="#eef2fb"/><text x="200" y="160" font-size="90" text-anchor="middle" dominant-baseline="central">🛍️</text></svg>');
document.addEventListener('error', e => {
  const t = e.target;
  if (t && t.tagName === 'IMG' && !t.dataset.fallback) { t.dataset.fallback = '1'; t.src = PLACEHOLDER; }
}, true);

// warn clearly when the Python server is not running
async function checkServer() {
  try { await fetch(BASE + '/api/health'); }
  catch {
    const bar = document.createElement('div');
    bar.style.cssText = 'background:#d32f2f;color:#fff;padding:10px 16px;text-align:center;font-size:14px;position:relative;z-index:99';
    bar.innerHTML = '⚠️ ' + OFFLINE_MSG.replace('http://localhost:8000', '<b>http://localhost:8000</b>');
    document.body.prepend(bar);
  }
}

document.addEventListener('DOMContentLoaded', () => { buildHeader(); refreshCartCount(); checkServer(); });
