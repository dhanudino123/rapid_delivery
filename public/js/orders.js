if (!API.requireLogin()) throw new Error('login required');
const STEPS = [['PLACED', 'Placed'], ['PACKED', 'Packed'], ['SHIPPED', 'Shipped'], ['OUT_FOR_DELIVERY', 'Out for delivery'], ['DELIVERED', 'Delivered']];
const LABEL = { PLACED: 'Order Confirmed', PACKED: 'Packed', SHIPPED: 'Shipped', OUT_FOR_DELIVERY: 'Out for Delivery', DELIVERED: 'Delivered', CANCELLED: 'Cancelled' };
let all = [], statusFilter = 'ALL', open = new Set();
const placedId = new URLSearchParams(location.search).get('placed');

function statusLine(o) {
  if (o.status === 'DELIVERED') return `<span class="dot"></span> Delivered`;
  if (o.status === 'CANCELLED') return `<span class="dot cancel"></span> Cancelled${o.payment_status === 'REFUNDED' ? ' · Refund initiated' : ''}`;
  return `<span class="dot wait"></span> ${LABEL[o.status]}<br><small class="muted" style="font-weight:400">Expected by ${o.expected_delivery}</small>`;
}

function timeline(o) {
  const ev = Object.fromEntries(o.events.map(e => [e.status, e.created_at]));
  if (o.status === 'CANCELLED') {
    return `<div class="timeline"><div class="t-step done"><i>✓</i>Placed<small>${ev.PLACED ? dateTimeFmt(ev.PLACED) : ''}</small></div>
      <div class="t-step cancel"><i>✕</i>Cancelled<small>${ev.CANCELLED ? dateTimeFmt(ev.CANCELLED) : ''}</small></div></div>`;
  }
  const idx = STEPS.findIndex(s => s[0] === o.status);
  return `<div class="timeline">${STEPS.map(([k, l], i) =>
    `<div class="t-step ${i <= idx ? 'done' : ''}"><i>${i <= idx ? '✓' : ''}</i>${l}<small>${ev[k] ? dateTimeFmt(ev[k]) : ''}</small></div>`).join('')}</div>`;
}

function render() {
  const q = document.getElementById('order-search').value.trim().toLowerCase();
  const list = all.filter(o => (statusFilter === 'ALL' || o.status === statusFilter) &&
    (!q || o.items.some(i => i.name.toLowerCase().includes(q)) || String(o.id) === q));
  const box = document.getElementById('orders');
  if (!list.length) {
    box.innerHTML = `<div class="box empty-box"><div class="big">📦</div><h2>${all.length ? 'No matching orders' : 'No orders yet'}</h2><a class="btn small" href="index.html">Start shopping</a></div>`; return;
  }
  box.innerHTML = list.map(o => `<div class="order" id="order-${o.id}">
    <div class="order-top"><span>ORDER <b>#${o.id}</b></span><span>Placed on <b>${dateFmt(o.created_at)}</b></span>
      <span>Total <b>${rupee(o.total)}</b></span><span>Payment <b>${esc(o.payment_label)}</b> · ${esc(o.payment_detail || '')} (${esc(o.payment_status)})${o.payment_ref ? ` · <small>Txn ${esc(o.payment_ref)}</small>` : ''}</span>
      <span class="pill ${o.status}">${LABEL[o.status]}</span></div>
    ${o.items.map(i => `<div class="order-item"><a href="product.html?id=${i.product_id}"><img src="${esc(i.image)}" alt=""></a>
      <div><a href="product.html?id=${i.product_id}"><b>${esc(i.name)}</b></a><div class="muted">Qty: ${i.qty}</div></div>
      <div><b>${rupee(i.price * i.qty)}</b></div><div class="status">${statusLine(o)}</div></div>`).join('')}
    <div class="order-foot">
      <span class="muted">📍 ${esc(o.ship_name)}, ${esc(o.ship_address)}</span>
      <button class="link-btn" data-track="${o.id}">${open.has(o.id) ? 'Hide tracking' : 'Track order'}</button>
      ${o.status === 'DELIVERED' ? `<a class="link-btn" href="product.html?id=${o.items[0].product_id}#reviews">★ Rate & Review</a>` : ''}
      ${o.can_cancel ? `<button class="link-btn red" data-cancel="${o.id}">Cancel order</button>` : ''}</div>
    ${open.has(o.id) ? timeline(o) : ''}</div>`).join('');
}

function renderFilter() {
  const opts = [['ALL', 'All orders'], ...Object.entries(LABEL)];
  const counts = Object.fromEntries(opts.map(([k]) => [k, k === 'ALL' ? all.length : all.filter(o => o.status === k).length]));
  document.getElementById('status-filter').innerHTML = opts.map(([k, l]) =>
    `<a href="#" data-s="${k}" class="${statusFilter === k ? 'on' : ''}">${l} <span class="muted">(${counts[k]})</span></a>`).join('');
}

document.getElementById('status-filter').addEventListener('click', e => {
  const a = e.target.closest('[data-s]'); if (!a) return; e.preventDefault(); statusFilter = a.dataset.s; renderFilter(); render();
});
document.getElementById('order-search-btn').onclick = render;
document.getElementById('order-search').addEventListener('keydown', e => { if (e.key === 'Enter') render(); });
document.getElementById('orders').addEventListener('click', async e => {
  const t = e.target.closest('[data-track]'), c = e.target.closest('[data-cancel]');
  if (t) { const id = +t.dataset.track; open.has(id) ? open.delete(id) : open.add(id); render(); }
  if (c && confirm('Cancel this order?')) {
    try { const u = await API.post(`/api/orders/${c.dataset.cancel}/cancel`);
      all = all.map(o => (o.id === u.id ? u : o)); renderFilter(); render(); toast('Order cancelled'); }
    catch (err) { toast(err.message); }
  }
});

(async () => {
  try {
    all = await API.get('/api/orders');
    if (placedId) {
      open.add(+placedId);
      document.getElementById('placed-banner').innerHTML = `<div class="banner-ok">🎉 <b>Order #${esc(placedId)} placed successfully!</b> Thank you for shopping with Flipcart.</div>`;
    }
    renderFilter(); render();
    if (placedId) document.getElementById('order-' + placedId)?.scrollIntoView({ block: 'center' });
  } catch (e) { document.getElementById('orders').innerHTML = `<div class="box empty-box">${esc(e.message)}</div>`; }
})();
