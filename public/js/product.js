const pid = new URLSearchParams(location.search).get('id');
const page = document.getElementById('page');

async function load() {
  let p;
  try { p = await API.get('/api/products/' + pid); }
  catch (e) { page.innerHTML = `<div class="empty-box"><div class="big">😕</div><h2>${esc(e.message)}</h2><a class="btn small" href="index.html">Go home</a></div>`; return; }
  document.title = p.name + ' – Flipcart';
  const out = p.stock === 0;
  page.innerHTML = `
  <div class="pdp">
    <div class="pdp-left">
      <div class="pdp-img"><img src="${esc(p.image)}" alt="${esc(p.name)}"></div>
      <div class="pdp-actions">
        <button class="btn cart" id="add" ${out ? 'disabled' : ''}>🛒 Add to cart</button>
        <button class="btn buy" id="buy" ${out ? 'disabled' : ''}>⚡ Buy now</button>
      </div>
    </div>
    <div class="pdp-right">
      <div class="crumbs"><a href="index.html">Home</a> › <a href="index.html?category=${p.category}">${esc(p.category_name)}</a> › ${esc(p.name)}</div>
      <h1>${esc(p.name)}</h1>
      <div>${rateBadge(p.rating)} <span class="muted">${Number(p.rating_count).toLocaleString('en-IN')} Ratings</span></div>
      <div class="green" style="margin-top:12px">Special price</div>
      <div class="pdp-price">${rupee(p.price)} <span class="mrp">${rupee(p.mrp)}</span> ${p.discount > 0 ? `<span class="off">${p.discount}% off</span>` : ''}</div>
      <div class="${out ? 'low-stock' : p.stock <= 10 ? 'low-stock' : 'green'}" style="margin-top:8px">${out ? 'Currently out of stock' : p.stock <= 10 ? `Hurry, only ${p.stock} left!` : 'In stock'}</div>
      <div class="offers"><h3>Available offers</h3><ul>
        ${p.offers.map(o => `<li><b>Coupon ${esc(o.code)}</b> – ${esc(o.description)}</li>`).join('')}
        <li><b>Free Delivery</b> on orders above ₹500</li></ul></div>
      <div class="pin-row"><b>Delivery</b> <input id="pin" maxlength="6" inputmode="numeric" placeholder="Enter pincode"><button class="link-btn" id="pin-btn">Check</button><span id="pin-msg"></span></div>
      <div class="sect"><h3>Description</h3><p>${esc(p.description)}. Sold by Flipcart Retail. 7 days replacement policy.</p></div>
    </div>
  </div>
  <div class="reviews" id="reviews"><h3 style="margin-top:0;font-size:18px;font-weight:500">Ratings & Reviews</h3>
    <div id="review-list">${p.reviews.length ? p.reviews.map(r => `<div class="review">${rateBadge(r.rating)} <b>${esc(r.user)}</b>
      <span class="muted"> · ${dateFmt(r.created_at)}</span>${r.comment ? `<p>${esc(r.comment)}</p>` : ''}</div>`).join('') : '<p class="muted">No reviews yet. Be the first to review this product!</p>'}</div>
    <div class="review-form"><b>Write a review</b>
      <select id="r-rating"><option value="5">5 ★ Excellent</option><option value="4">4 ★ Very good</option><option value="3">3 ★ Good</option><option value="2">2 ★ Poor</option><option value="1">1 ★ Terrible</option></select>
      <textarea id="r-comment" placeholder="Share your experience (optional)"></textarea>
      <button class="btn small" id="r-submit" style="justify-self:start">Submit review</button></div></div>
  ${p.related.length ? `<section class="panel"><div class="panel-head"><h2>Similar products</h2></div><div class="row-scroll">${p.related.map(productCard).join('')}</div></section>` : ''}`;

  const add = async (go) => {
    if (!API.requireLogin()) return;
    try {
      const cart = await API.post('/api/cart', { productId: p.id, quantity: 1 });
      document.getElementById('cart-count').textContent = cart.count;
      go ? location.href = 'checkout.html' : toast('Added to cart ✓');
    } catch (e) { toast(e.message); }
  };
  document.getElementById('add').onclick = () => add(false);
  document.getElementById('buy').onclick = () => add(true);
  document.getElementById('pin-btn').onclick = async () => {
    const msg = document.getElementById('pin-msg');
    try { const d = await API.get('/api/delivery?pincode=' + document.getElementById('pin').value.trim());
      msg.innerHTML = `<span class="green">Delivery by ${d.eta} | Free</span>`; }
    catch (e) { msg.innerHTML = `<span style="color:var(--red)">${esc(e.message)}</span>`; }
  };
  document.getElementById('r-submit').onclick = async () => {
    if (!API.requireLogin()) return;
    try {
      await API.post(`/api/products/${p.id}/reviews`, { rating: +document.getElementById('r-rating').value, comment: document.getElementById('r-comment').value });
      toast('Thanks for your review!'); load();
    } catch (e) { toast(e.message); }
  };
}
load();
