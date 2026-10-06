const form = document.getElementById('login-form') || document.getElementById('signup-form');
const msg = document.getElementById('msg');
const isSignup = form.id === 'signup-form';
form.addEventListener('submit', async e => {
  e.preventDefault();
  msg.className = 'form-msg'; msg.textContent = '';
  const btn = form.querySelector('button'); btn.disabled = true;
  try {
    const data = Object.fromEntries(new FormData(form));
    const { token, user } = await API.post(isSignup ? '/api/auth/signup' : '/api/auth/login', data);
    API.setSession(token, user);
    msg.className = 'form-msg success'; msg.textContent = isSignup ? 'Account created! Redirecting…' : 'Logged in! Redirecting…';
    const next = new URLSearchParams(location.search).get('next') || '';
    setTimeout(() => (location.href = /^[\w.-]+\.html(\?[\w=&%.-]*)?$/.test(next) ? next : 'index.html'), 400);
  } catch (err) { msg.className = 'form-msg error'; msg.textContent = err.message; btn.disabled = false; }
});

// show the demo-admin hint only when the server still uses the default admin password
fetch(BASE + '/api/health').then(r => r.json()).then(h => {
  const el = document.getElementById('demo-hint'); if (el && h.demo_admin) el.hidden = false;
}).catch(() => {});
