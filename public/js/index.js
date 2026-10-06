const params = new URLSearchParams(location.search);
const catStrip = document.getElementById('cat-strip');
let CATS = [];

const SLIDES = [
  { bg: 'linear-gradient(90deg,#2874f0,#6a85f7)', h: 'Big Billion Sale', p: 'Up to 70% off on Mobiles & Laptops', art: '📱', link: 'index.html?category=mobiles' },
  { bg: 'linear-gradient(90deg,#ff7e5f,#feb47b)', h: 'Fashion Fest', p: 'Shoes, jackets & bags from ₹399', art: '👟', link: 'index.html?category=fashion' },
  { bg: 'linear-gradient(90deg,#11998e,#38ef7d)', h: 'Electronics Carnival', p: 'TVs, speakers, cameras & more', art: '📺', link: 'index.html?category=electronics' },
  { bg: 'linear-gradient(90deg,#8e2de2,#e04ea6)', h: 'Kids Zone', p: 'Toys & games the little ones love', art: '🧸', link: 'index.html?category=toys' }
];

async function init() {
  CATS = await API.get('/api/categories');
  const active = params.get('category');
  catStrip.innerHTML = CATS.map(c =>
    `<a class="cat-item ${c.slug === active ? 'active' : ''}" href="index.html?category=${c.slug}"><span>${c.icon}</span>${esc(c.name)}</a>`).join('');
  const isList = ['q', 'category', 'sort', 'min_price', 'max_price', 'rating', 'all'].some(k => params.has(k));
  isList ? showList() : showHome();
}

/* ---------------- home ---------------- */
function showHome() {
  document.getElementById('home-view').hidden = false;
  const slides = document.getElementById('slides'), dots = document.getElementById('dots');
  slides.innerHTML = SLIDES.map((s, i) => `<div class="slide ${i ? '' : 'on'}" style="background:${s.bg}">
      <div><h2>${s.h}</h2><p>${s.p}</p><a class="cta" href="${s.link}">Shop now</a></div><div class="art">${s.art}</div></div>`).join('');
  dots.innerHTML = SLIDES.map((_, i) => `<button class="${i ? '' : 'on'}" data-i="${i}" aria-label="Slide ${i + 1}"></button>`).join('');
  let cur = 0, timer;
  const go = i => {
    cur = (i + SLIDES.length) % SLIDES.length;
    slides.querySelectorAll('.slide').forEach((el, k) => el.classList.toggle('on', k === cur));
    dots.querySelectorAll('button').forEach((el, k) => el.classList.toggle('on', k === cur));
  };
  const auto = () => { clearInterval(timer); timer = setInterval(() => go(cur + 1), 4500); };
  document.getElementById('car-prev').onclick = () => { go(cur - 1); auto(); };
  document.getElementById('car-next').onclick = () => { go(cur + 1); auto(); };
  dots.onclick = e => { const b = e.target.closest('button'); if (b) { go(+b.dataset.i); auto(); } };
  auto();

  const titles = { mobiles: 'Best of Mobiles', laptops: 'Laptops & Accessories', electronics: 'Top Deals on Electronics',
    fashion: 'Fashion Bestsellers', home: 'Home & Kitchen Essentials', beauty: 'Beauty & Personal Care',
    toys: 'Toys & Games', books: 'Bestselling Books', grocery: 'Fresh Grocery' };
  const rows = document.getElementById('home-rows');
  rows.innerHTML = CATS.map(c => `<section class="panel" id="row-${c.slug}" hidden>
      <div class="panel-head"><h2>${titles[c.slug] || c.name}</h2><a class="btn-view" href="index.html?category=${c.slug}">View all</a></div>
      <div class="row-scroll"></div></section>`).join('');
  CATS.forEach(async c => {
    try {
      const items = await API.get(`/api/products?category=${c.slug}&limit=8&sort=relevance`);
      if (!items.length) return;
      const sec = document.getElementById('row-' + c.slug);
      sec.querySelector('.row-scroll').innerHTML = items.map(productCard).join('');
      sec.hidden = false;
    } catch {}
  });
}

/* ---------------- listing ---------------- */
function url(changes) {
  const p = new URLSearchParams(location.search);
  Object.entries(changes).forEach(([k, v]) => (v === null || v === '' ? p.delete(k) : p.set(k, v)));
  p.set('all', '1'); // keep list mode even when no filter is set
  if (p.get('q') || p.get('category') || p.get('sort') || p.get('min_price') || p.get('max_price') || p.get('rating')) p.delete('all');
  return 'index.html?' + p.toString();
}

async function showList() {
  document.getElementById('list-view').hidden = false;
  const q = params.get('q') || '', cat = params.get('category') || '', sort = params.get('sort') || 'relevance';
  const minP = params.get('min_price') || '', maxP = params.get('max_price') || '', rating = params.get('rating') || '';
  const catName = (CATS.find(c => c.slug === cat) || {}).name;

  const priceRanges = [['Under ₹500', '', 500], ['₹500 – ₹2,000', 500, 2000], ['₹2,000 – ₹10,000', 2000, 10000], ['Over ₹10,000', 10000, '']];
  document.getElementById('filters').innerHTML = `<h3>Filters</h3>
    <div class="f-block"><h4>Categories</h4>
      <a href="${url({ category: null })}" class="${!cat ? 'on' : ''}">All categories</a>
      ${CATS.map(c => `<a href="${url({ category: c.slug })}" class="${c.slug === cat ? 'on' : ''}">${c.icon} ${esc(c.name)}</a>`).join('')}</div>
    <div class="f-block"><h4>Price</h4>
      <a href="${url({ min_price: null, max_price: null })}" class="${!minP && !maxP ? 'on' : ''}">Any price</a>
      ${priceRanges.map(([l, lo, hi]) => `<a href="${url({ min_price: lo, max_price: hi })}" class="${String(lo) === minP && String(hi) === maxP ? 'on' : ''}">${l}</a>`).join('')}</div>
    <div class="f-block"><h4>Customer Ratings</h4>
      <a href="${url({ rating: null })}" class="${!rating ? 'on' : ''}">Any</a>
      <a href="${url({ rating: 4 })}" class="${rating === '4' ? 'on' : ''}">4★ & above</a>
      <a href="${url({ rating: 3 })}" class="${rating === '3' ? 'on' : ''}">3★ & above</a></div>`;

  const sorts = [['relevance', 'Popularity'], ['price_asc', 'Price -- Low to High'], ['price_desc', 'Price -- High to Low'], ['rating', 'Rating'], ['discount', 'Discount'], ['newest', 'Newest First']];
  document.getElementById('sortbar').innerHTML = '<b>Sort By</b>' +
    sorts.map(([k, l]) => `<a href="${url({ sort: k === 'relevance' ? null : k })}" class="${sort === k ? 'on' : ''}">${l}</a>`).join('');
  document.getElementById('list-title').textContent = q ? `Showing results for "${q}"` : (catName || 'All products');

  const api = new URLSearchParams();
  if (q) api.set('q', q); if (cat) api.set('category', cat); api.set('sort', sort);
  if (minP) api.set('min_price', minP); if (maxP) api.set('max_price', maxP); if (rating) api.set('rating', rating);
  const grid = document.getElementById('grid');
  grid.innerHTML = '<div class="empty-box">Loading…</div>';
  try {
    const items = await API.get('/api/products?' + api);
    document.getElementById('list-count').textContent = `${items.length} item${items.length === 1 ? '' : 's'}`;
    document.title = (q || catName || 'All products') + ' – Flipcart';
    grid.innerHTML = items.length ? items.map(productCard).join('')
      : `<div class="empty-box" style="grid-column:1/-1"><div class="big">🔎</div><h2>Sorry, no results found!</h2><p>Try phone, laptop, shoes, tv, fan or book — or remove some filters.</p><a class="btn small" href="index.html?all=1">Clear filters</a></div>`;
  } catch (e) { grid.innerHTML = `<div class="empty-box">${esc(e.message)}</div>`; }
}

init().catch(e => {
  document.querySelector('main').innerHTML = `<div class="empty-box"><div class="big">🔌</div><h2>Can't load products</h2><p>${esc(e.message)}</p></div>`;
});
