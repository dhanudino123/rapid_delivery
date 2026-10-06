const itemsBox = document.getElementById('cart-items');
let promo = sessionStorage.getItem('fc_promo') || '';
document.getElementById('promo-input').value = promo;

function render(cart) {
  document.getElementById('cart-count').textContent = cart.count;
  const has = cart.items.length > 0;
  document.getElementById('price-box').hidden = !has;
  document.getElementById('place-bar').hidden = !has;
  document.querySelector('.box-head').textContent = `My Cart (${cart.count})`;
  if (!has) {
    itemsBox.innerHTML = `<div class="empty-box"><div class="big">🛒</div><h2>Your cart is empty!</h2><p>Add items to it now.</p><a class="btn small" href="index.html">Shop now</a></div>`;
    return;
  }
  itemsBox.innerHTML = cart.items.map(i => {
    const off = Math.round((i.mrp - i.price) * 100 / i.mrp);
    return `<div class="cart-row"><a href="product.html?id=${i.id}"><img src="${esc(i.image)}" alt=""></a>
      <div><a href="product.html?id=${i.id}"><h3>${esc(i.name)}</h3></a>
        <div class="price-line"><span class="mrp">${rupee(i.mrp * i.qty)}</span><span class="price">${rupee(i.price * i.qty)}</span><span class="off">${off}% off</span></div>
        ${i.qty >= i.stock ? `<div class="low-stock">Max stock reached (${i.stock})</div>` : ''}
        <div class="qty-line"><div class="stepper">
          <button data-act="dec" data-id="${i.id}" data-qty="${i.qty}" aria-label="Decrease">−</button><span>${i.qty}</span>
          <button data-act="inc" data-id="${i.id}" data-qty="${i.qty}" ${i.qty >= i.stock ? 'disabled' : ''} aria-label="Increase">+</button></div>
          <button class="link-btn red" data-act="rm" data-id="${i.id}">REMOVE</button></div></div></div>`;
  }).join('');

  const row = (l, v, c = '') => `<div class="pr ${c}"><span>${l}</span><span>${v}</span></div>`;
  document.getElementById('price-rows').innerHTML =
    row(`Price (${cart.count} item${cart.count > 1 ? 's' : ''})`, rupee(cart.mrp_total)) +
    row('Discount', `<span class="green">− ${rupee(cart.discount)}</span>`) +
    (cart.coupon ? row(`Coupon (${cart.coupon_code})`, `<span class="green">− ${rupee(cart.coupon)}</span>`) : '') +
    row('Delivery Charges', cart.delivery ? rupee(cart.delivery) : '<span class="green">FREE</span>') +
    row('Total Amount', rupee(cart.total), 'total');
  document.getElementById('save-msg').textContent = `You will save ${rupee(cart.savings)} on this order`;
  const m = document.getElementById('promo-msg');
  m.className = 'coupon-msg ' + (cart.promoError ? 'err' : cart.coupon_code ? 'ok' : '');
  m.textContent = cart.promoError || (cart.coupon_code ? `Coupon ${cart.coupon_code} applied ✓` : '');
  if (cart.promoError) { promo = ''; sessionStorage.removeItem('fc_promo'); }
}

async function load() {
  if (!API.requireLogin()) return;
  try { render(await API.get('/api/cart' + (promo ? '?promo=' + encodeURIComponent(promo) : ''))); }
  catch (e) { itemsBox.innerHTML = `<div class="empty-box">${esc(e.message)}</div>`; }
}

itemsBox.addEventListener('click', async e => {
  const b = e.target.closest('[data-act]'); if (!b) return;
  const id = b.dataset.id, qty = +b.dataset.qty, q = promo ? '?promo=' + encodeURIComponent(promo) : '';
  try {
    if (b.dataset.act === 'rm') render(await API.del('/api/cart/' + id + q));
    else render(await API.patch('/api/cart/' + id, { quantity: b.dataset.act === 'inc' ? qty + 1 : qty - 1, promo }));
  } catch (err) { toast(err.message); }
});

document.getElementById('apply-promo').onclick = () => {
  promo = document.getElementById('promo-input').value.trim().toUpperCase();
  promo ? sessionStorage.setItem('fc_promo', promo) : sessionStorage.removeItem('fc_promo');
  load();
};
load();
