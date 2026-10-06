if (!API.requireLogin()) throw new Error('login required');
const STATUSES = ['PLACED', 'PACKED', 'SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED'];
const $ = id => document.getElementById(id);
let CATS = [];
const FLOW = ['PLACED', 'PACKED', 'SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED'];
const nextStatuses = cur => [...FLOW.slice(FLOW.indexOf(cur)), 'CANCELLED'];

document.getElementById('tabs').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  document.querySelectorAll('#tabs button').forEach(x => x.classList.toggle('on', x === b));
  ['dash', 'orders', 'products'].forEach(t => ($('tab-' + t).hidden = t !== b.dataset.t));
  ({ dash: loadDash, orders: loadOrders, products: loadProducts })[b.dataset.t]();
});

async function loadDash() {
  const s = await API.get('/api/admin/stats');
  $('tab-dash').innerHTML = `<div class="stats">
      <div class="stat"><b>${s.orders}</b><span>Total orders</span></div>
      <div class="stat"><b>${rupee(s.revenue)}</b><span>Revenue (excl. cancelled)</span></div>
      <div class="stat"><b>${s.users}</b><span>Customers</span></div>
      <div class="stat"><b>${s.products}</b><span>Products</span></div></div>
    <div class="two-col">
      <div class="box"><div class="box-head">Orders by status</div><table class="tbl"><tbody>
        ${STATUSES.map(k => `<tr><td><span class="pill ${k}">${k.replaceAll('_', ' ')}</span></td><td><b>${s.by_status[k] || 0}</b></td></tr>`).join('')}</tbody></table></div>
      <div class="box"><div class="box-head">Top selling</div><table class="tbl"><tbody>
        ${s.top_products.map(t => `<tr><td>${esc(t.name)}</td><td><b>${t.sold}</b> sold</td></tr>`).join('') || '<tr><td class="muted">No sales yet</td></tr>'}</tbody></table>
        <div class="box-head" style="border-top:1px solid var(--line)">Low stock (≤ 10)</div><table class="tbl"><tbody>
        ${s.low_stock.map(t => `<tr><td>${esc(t.name)}</td><td class="low-stock">${t.stock} left</td></tr>`).join('') || '<tr><td class="muted">All good 👍</td></tr>'}</tbody></table></div></div>`;
}

async function loadOrders() {
  const orders = await API.get('/api/admin/orders');
  $('tab-orders').innerHTML = `<div class="table-scroll"><table class="tbl"><thead><tr><th>#</th><th>Customer</th><th>Items</th><th>Total</th><th>Payment</th><th>Date</th><th>Status</th></tr></thead><tbody>
    ${orders.map(o => `<tr><td>${o.id}</td><td>${esc(o.customer)}<br><small class="muted">${esc(o.email)}</small></td>
      <td>${o.items.map(i => `${esc(i.name)} × ${i.qty}`).join('<br>')}</td><td><b>${rupee(o.total)}</b></td>
      <td>${esc(o.payment_label)}<br><small class="muted">${o.payment_status}</small></td><td>${dateFmt(o.created_at)}</td>
      <td>${['DELIVERED', 'CANCELLED'].includes(o.status) ? `<span class="pill ${o.status}">${o.status}</span>` :
        `<select data-oid="${o.id}">${nextStatuses(o.status).map(s => `<option ${s === o.status ? 'selected' : ''}>${s}</option>`).join('')}</select>`}</td></tr>`).join('')
      || '<tr><td colspan="7" class="muted">No orders yet</td></tr>'}</tbody></table></div>`;
}
$('tab-orders').addEventListener('change', async e => {
  const sel = e.target.closest('select[data-oid]'); if (!sel) return;
  try { await API.patch(`/api/admin/orders/${sel.dataset.oid}/status`, { status: sel.value }); toast('Status updated'); loadOrders(); }
  catch (err) { toast(err.message); loadOrders(); }
});

async function loadProducts() {
  if (!CATS.length) CATS = await API.get('/api/categories');
  const items = await API.get('/api/products?sort=newest');
  $('tab-products').innerHTML = `<div class="box" style="margin-top:8px"><div class="box-head">Add a new product</div>
    <form id="prod-form" class="step-body form-grid" novalidate>
      <input class="field-in" name="name" placeholder="Product name" required>
      <select class="field-in" name="category">${CATS.map(c => `<option value="${c.slug}">${esc(c.name)}</option>`).join('')}</select>
      <input class="field-in" name="price" type="number" min="1" placeholder="Selling price ₹" required>
      <input class="field-in" name="mrp" type="number" min="1" placeholder="MRP ₹" required>
      <input class="field-in" name="stock" type="number" min="0" placeholder="Stock" required>
      <input class="field-in" name="emoji" placeholder="Emoji for image (e.g. 🎮)" maxlength="4">
      <input class="field-in full" name="description" placeholder="Description">
      <input class="field-in full" name="image" placeholder="Image URL (optional – leave blank to auto-generate)">
      <div class="full"><div class="form-msg" id="prod-msg"></div><button class="btn small" type="submit">Add product</button></div></form></div>
    <div class="table-scroll"><table class="tbl"><thead><tr><th></th><th>Product</th><th>Category</th><th>Price ₹</th><th>MRP ₹</th><th>Stock</th><th></th></tr></thead><tbody>
    ${items.map(p => `<tr data-pid="${p.id}"><td><img src="${esc(p.image)}" width="44" height="44" style="object-fit:contain" alt=""></td><td>${esc(p.name)}</td><td>${esc(p.category_name)}</td>
      <td><input type="number" min="1" data-f="price" value="${p.price}"></td><td><input type="number" min="1" data-f="mrp" value="${p.mrp}"></td>
      <td><input type="number" min="0" data-f="stock" value="${p.stock}"></td><td><button class="btn small" data-save>Save</button></td></tr>`).join('')}</tbody></table></div>`;
}
$('tab-products').addEventListener('click', async e => {
  const b = e.target.closest('[data-save]'); if (!b) return;
  const tr = b.closest('tr'), body = {};
  tr.querySelectorAll('input[data-f]').forEach(i => (body[i.dataset.f] = +i.value));
  try { await API.patch('/api/admin/products/' + tr.dataset.pid, body); toast('Product updated'); } catch (err) { toast(err.message); }
});
$('tab-products').addEventListener('submit', async e => {
  e.preventDefault();
  const msg = $('prod-msg'); msg.className = 'form-msg'; msg.textContent = '';
  try { await API.post('/api/admin/products', Object.fromEntries(new FormData(e.target))); toast('Product added'); loadProducts(); }
  catch (err) { msg.className = 'form-msg error'; msg.textContent = err.message; }
});

(async () => {
  try { await API.get('/api/auth/me'); const u = API.user();
    if (!u || !u.is_admin) { document.querySelector('main').innerHTML = '<div class="empty-box"><div class="big">🔒</div><h2>Admin access only</h2><a class="btn small" href="login.html?next=admin.html">Log in as admin</a></div>'; return; }
    loadDash();
  } catch { API.requireLogin(); }
})();
