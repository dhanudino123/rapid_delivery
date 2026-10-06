if (!API.requireLogin()) throw new Error('login required');
const promo = sessionStorage.getItem('fc_promo') || '';
let addresses = [], selected = null, cart = null;

async function loadCart() {
  cart = await API.get('/api/cart' + (promo ? '?promo=' + encodeURIComponent(promo) : ''));
  if (!cart.items.length) { location.href = 'cart.html'; return; }
  document.getElementById('order-summary').innerHTML = cart.items.map(i =>
    `<div class="sum-item"><img src="${esc(i.image)}" alt=""><div style="flex:1"><b>${esc(i.name)}</b><div class="muted">Qty: ${i.qty}</div></div><b>${rupee(i.price * i.qty)}</b></div>`).join('') +
    '<p class="muted" style="margin-bottom:0">Order confirmation will be shown on the My Orders page.</p>';
  const row = (l, v, c = '') => `<div class="pr ${c}"><span>${l}</span><span>${v}</span></div>`;
  document.getElementById('price-rows').innerHTML =
    row(`Price (${cart.count} items)`, rupee(cart.mrp_total)) + row('Discount', `<span class="green">− ${rupee(cart.discount)}</span>`) +
    (cart.coupon ? row(`Coupon (${cart.coupon_code})`, `<span class="green">− ${rupee(cart.coupon)}</span>`) : '') +
    row('Delivery Charges', cart.delivery ? rupee(cart.delivery) : '<span class="green">FREE</span>') + row('Total Payable', rupee(cart.total), 'total');
  document.getElementById('save-msg').textContent = `You will save ${rupee(cart.savings)} on this order`;
  if (typeof showForm === 'function') showForm();
}

function renderAddresses() {
  const box = document.getElementById('addr-list');
  if (!addresses.length) { box.innerHTML = '<p class="muted">No saved addresses yet. Please add one.</p>'; document.getElementById('addr-form').hidden = false; return; }
  if (!selected || !addresses.some(a => a.id === selected)) selected = addresses[0].id;
  box.innerHTML = addresses.map(a => `<label class="addr ${a.id === selected ? 'sel' : ''}">
    <input type="radio" name="addr" value="${a.id}" ${a.id === selected ? 'checked' : ''}>
    <div style="flex:1"><b>${esc(a.name)}</b> <span class="tag">${esc(a.kind)}</span> <b style="margin-left:12px">${esc(a.phone)}</b>
      <div>${esc(a.line1)}, ${esc(a.city)}, ${esc(a.state)} - <b>${esc(a.pincode)}</b></div></div>
    <button type="button" class="link-btn red" data-del="${a.id}">Delete</button></label>`).join('');
}

document.getElementById('addr-list').addEventListener('click', async e => {
  const del = e.target.closest('[data-del]');
  if (del) { e.preventDefault(); await API.del('/api/addresses/' + del.dataset.del); await loadAddresses(); }
});
document.getElementById('addr-list').addEventListener('change', e => { if (e.target.name === 'addr') { selected = +e.target.value; renderAddresses(); } });
document.getElementById('toggle-addr').onclick = () => { const f = document.getElementById('addr-form'); f.hidden = !f.hidden; };

document.getElementById('addr-form').addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target, msg = document.getElementById('addr-msg'); msg.className = 'form-msg'; msg.textContent = '';
  try {
    const a = await API.post('/api/addresses', Object.fromEntries(new FormData(f)));
    selected = a.id; f.reset(); f.hidden = true; await loadAddresses();
  } catch (err) { msg.className = 'form-msg error'; msg.textContent = err.message; }
});

async function loadAddresses() { addresses = await API.get('/api/addresses'); renderAddresses(); }

/* ---------------- payment ---------------- */
const $ = id => document.getElementById(id);
const method = () => document.querySelector('input[name=pay]:checked').value;

function showForm() {
  document.querySelectorAll('.pay-form').forEach(f => (f.hidden = f.dataset.for !== method()));
  $('order-msg').textContent = '';
  $('place').textContent = method() === 'COD' ? 'Place order' : `Pay ${cart ? rupee(cart.total) : ''} & place order`;
}
document.querySelectorAll('input[name=pay]').forEach(r => r.addEventListener('change', showForm));

API.get('/api/payment/options').then(o => {
  $('bank').innerHTML += o.banks.map(b => `<option>${esc(b)}</option>`).join('');
}).catch(() => {});

// friendly input formatting
$('card_number').addEventListener('input', e => {
  e.target.value = e.target.value.replace(/\D/g, '').slice(0, 19).replace(/(\d{4})(?=\d)/g, '$1 ');
});
$('expiry').addEventListener('input', e => {
  let v = e.target.value.replace(/\D/g, '').slice(0, 4);
  e.target.value = v.length > 2 ? v.slice(0, 2) + '/' + v.slice(2) : v;
});
$('cvv').addEventListener('input', e => (e.target.value = e.target.value.replace(/\D/g, '')));

function luhn(num) {
  let sum = 0, flip = false;
  for (let i = num.length - 1; i >= 0; i--) { let n = +num[i]; if (flip) { n *= 2; if (n > 9) n -= 9; } sum += n; flip = !flip; }
  return sum % 10 === 0;
}

// returns [payment details object, error message]
function collectPayment() {
  const m = method();
  if (m === 'UPI') {
    const upi = $('upi_id').value.trim();
    if (!/^[a-z0-9][a-z0-9._-]+@[a-z][a-z0-9]+$/i.test(upi)) return [null, 'Enter a valid UPI ID (for example name@okhdfcbank)'];
    return [{ upi_id: upi }];
  }
  if (m === 'CARD') {
    const num = $('card_number').value.replace(/\s/g, ''), exp = $('expiry').value, cvv = $('cvv').value;
    if (num.length < 13 || !luhn(num)) return [null, 'Enter a valid card number'];
    if (!$('card_name').value.trim()) return [null, 'Enter the name on the card'];
    const mm = exp.match(/^(\d{2})\/(\d{2})$/);
    if (!mm || +mm[1] < 1 || +mm[1] > 12) return [null, 'Enter the expiry date as MM/YY'];
    const now = new Date();
    if (2000 + +mm[2] < now.getFullYear() || (2000 + +mm[2] === now.getFullYear() && +mm[1] < now.getMonth() + 1)) return [null, 'This card has expired'];
    if (!/^\d{3,4}$/.test(cvv)) return [null, 'Enter the CVV from the back of your card'];
    return [{ card_number: num, card_name: $('card_name').value.trim(), expiry: exp, cvv }];
  }
  if (m === 'NETBANKING') {
    if (!$('bank').value) return [null, 'Please choose your bank'];
    return [{ bank: $('bank').value }];
  }
  return [{}];
}

/* full-screen "processing / success / failed" box */
function overlay(html) {
  let o = $('pay-overlay');
  if (!o) { o = document.createElement('div'); o.id = 'pay-overlay'; o.className = 'modal-back'; document.body.appendChild(o); }
  o.innerHTML = `<div class="modal">${html}</div>`; o.hidden = false;
}
const closeOverlay = () => { const o = $('pay-overlay'); if (o) o.hidden = true; };

$('place').onclick = async () => {
  const msg = $('order-msg'), btn = $('place');
  msg.textContent = '';
  if (!selected) { msg.textContent = 'Please add and select a delivery address (step 2).'; $('addr-list').scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
  const [payment, err] = collectPayment();
  if (err) { msg.textContent = err; msg.scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }

  btn.disabled = true;
  const online = method() !== 'COD';
  overlay(`<div class="spinner"></div><h3>${online ? 'Processing your payment…' : 'Placing your order…'}</h3>
    <p class="muted">${online ? `Paying ${rupee(cart.total)} securely. Please do not refresh or press back.` : 'Just a moment.'}</p>`);
  try {
    const [order] = await Promise.all([
      API.post('/api/orders', { address_id: selected, payment_method: method(), payment, promo }),
      new Promise(r => setTimeout(r, online ? 1600 : 500))   // short pause so the user can see the processing step
    ]);
    sessionStorage.removeItem('fc_promo');
    overlay(`<div class="tick ok">✓</div><h3>${online ? 'Payment successful' : 'Order placed'}</h3>
      <p>${online ? `${rupee(order.total)} paid via ${esc(order.payment_detail)}<br><small class="muted">Transaction ID: ${esc(order.payment_ref)}</small>` : `Pay ${rupee(order.total)} on delivery.`}</p>
      <p class="muted">Redirecting to your order…</p>`);
    setTimeout(() => (location.href = 'orders.html?placed=' + order.id), 1500);
  } catch (e) {
    btn.disabled = false;
    if (e.status === 401) { location.href = 'login.html?next=checkout.html'; return; }
    overlay(`<div class="tick bad">✕</div><h3>${e.status === 402 ? 'Payment failed' : 'Could not place order'}</h3>
      <p>${esc(e.message)}</p>${e.status === 402 ? '<p class="muted">You have not been charged. Your cart is safe.</p>' : ''}
      <button class="btn small" id="pay-retry">Try again / change method</button>`);
    $('pay-retry').onclick = closeOverlay;
  }
};
showForm();

(async () => {
  const u = API.user();
  document.getElementById('login-info').innerHTML = u ? `<b>${esc(u.name)}</b> <span class="muted">${esc(u.email)}</span>` : '';
  try { await Promise.all([loadCart(), loadAddresses()]); } catch (e) { toast(e.message); }
})();
