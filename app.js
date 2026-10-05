// Forge landing: demo stepper (auto-play), copy buttons, plan preselect, static order form (mailto or Formspree).
(() => {
  const steps = [...document.querySelectorAll('.step')], panes = [...document.querySelectorAll('.pane')];
  const title = document.getElementById('scr-title');
  let cur = 0, timer = null, paused = false;
  const show = i => {
    cur = i;
    steps.forEach((s, k) => { s.classList.toggle('on', k === i); s.setAttribute('aria-selected', k === i); });
    panes.forEach((p, k) => p.classList.toggle('on', k === i));
    title.textContent = panes[i].dataset.title;
    // restart progress bar animation
    const bar = steps[i].querySelector('.bar i'); bar.style.animation = 'none'; void bar.offsetWidth; bar.style.animation = '';
  };
  const play = () => { clearInterval(timer); timer = setInterval(() => { if (!paused) show((cur + 1) % steps.length); }, 5500); };
  steps.forEach((s, i) => s.addEventListener('click', () => { show(i); play(); }));
  const scr = document.querySelector('.screen');
  scr.addEventListener('mouseenter', () => paused = true); scr.addEventListener('mouseleave', () => paused = false);
  play();

  document.querySelectorAll('.copy').forEach(b => b.addEventListener('click', async () => {
    const txt = b.previousElementSibling.innerText.split('\n').filter(l => !l.trim().startsWith('#')).map(l => l.replace(/\s+#.*$/, '')).join('\n').trim();
    try { await navigator.clipboard.writeText(txt); } catch { const t = document.createElement('textarea'); t.value = txt; document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove(); }
    b.textContent = 'Copied'; b.classList.add('done'); setTimeout(() => { b.textContent = 'Copy'; b.classList.remove('done'); }, 1600);
  }));

  const sel = document.getElementById('f-plan');
  document.querySelectorAll('[data-plan]').forEach(a => a.addEventListener('click', () => { sel.value = a.dataset.plan; }));

  const form = document.getElementById('orderForm'), msg = document.getElementById('formMsg');
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(form));
    if (d.website_url) return; // honeypot
    if (!d.name.trim() || !/^\S+@\S+\.\S+$/.test(d.email)) { msg.textContent = 'Please add your name and a valid email.'; return; }
    const ep = form.dataset.endpoint;
    if (ep) {
      try {
        const r = await fetch(ep, { method: 'POST', headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify(d) });
        if (r.ok) { form.reset(); msg.textContent = 'Thanks! We will reply within 24 hours.'; return; }
      } catch {}
    }
    const body = `Name: ${d.name}\nEmail: ${d.email}\nPlan: ${d.plan}\nGitHub: ${d.github || '-'}\n\nWhat I build:\n${d.skills || '-'}\n`;
    location.href = `mailto:proximus.desk@gmail.com?subject=${encodeURIComponent('Forge order: ' + d.plan)}&body=${encodeURIComponent(body)}`;
    msg.textContent = 'Opening your email app… if nothing happens, write to proximus.desk@gmail.com.';
  });

  const io = new IntersectionObserver(es => es.forEach(x => { if (x.isIntersecting) { x.target.classList.add('in'); io.unobserve(x.target); } }), { threshold: .12 });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));
})();
