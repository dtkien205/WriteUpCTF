/* Shared helpers: API wrapper, toasts, cart badge, add-to-cart, newsletter. */

async function api(url, method = 'GET', body) {
  const opts = {method, headers: {}};
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `Request failed (${res.status})`);
    err.fields = data.fields;
    throw err;
  }
  return data;
}

function updateBadge(count) {
  const badge = document.getElementById('cart-badge');
  if (!badge) return;
  badge.textContent = count;
  badge.hidden = !count;
  badge.classList.remove('pop');
  void badge.offsetWidth; // restart animation
  badge.classList.add('pop');
}

function toast(message, type = 'ok') {
  const root = document.getElementById('toast-root');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => el.classList.add('show'), 10);
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 400);
  }, 2800);
}

async function addToCart(productId, qty = 1) {
  try {
    const cart = await api('/api/cart', 'POST', {product_id: productId, qty});
    updateBadge(cart.count);
    toast(`Added to cart 🛒 (${cart.count} item${cart.count === 1 ? '' : 's'})`);
    return cart;
  } catch (err) {
    toast(err.message, 'err');
  }
}

// Any button with data-add-to-cart="<id>" adds one unit.
document.addEventListener('click', e => {
  const btn = e.target.closest('[data-add-to-cart]');
  if (btn) addToCart(+btn.dataset.addToCart, 1);
});

// Footer newsletter form (present on every page).
document.getElementById('newsletter-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const msg = document.getElementById('newsletter-msg');
  try {
    const r = await api('/api/newsletter', 'POST', {email: e.target.email.value});
    msg.textContent = r.message;
    msg.className = 'form-msg ok';
    e.target.reset();
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'form-msg err';
  }
});
