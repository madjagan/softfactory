/* Support desk in-app widget. One tag in the product's page:
 *
 *   <script src="https://support.example.com/widget.js" data-token="{{ signed token }}" data-app-version="3.4.1" async></script>
 *
 * data-token is signed by the product's backend (support/app.py sign_widget_token) with
 * SUPPORT_WIDGET_SECRET; it names the org and the user, so the customer types neither.
 */
(function () {
  const me = document.currentScript;
  if (!me || !me.dataset.token) return;
  const base = new URL('.', me.src).href;
  const token = me.dataset.token, appVersion = me.dataset.appVersion || '', label = me.dataset.label || 'Help';
  const call = async (path, init) => {
    const r = await fetch(base + path, Object.assign({}, init, { headers: Object.assign({ 'X-Widget-Token': token }, init.headers || {}) }));
    const data = await r.json().catch(() => null);
    if (!r.ok) throw new Error((data && data.error) || r.statusText);
    return data;
  };

  const host = document.createElement('div');
  const root = host.attachShadow({ mode: 'open' });
  root.innerHTML = `<style>
    :host { all: initial; }
    * { box-sizing: border-box; font: 14px/1.45 -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; }
    .fab { position: fixed; right: 20px; bottom: 20px; z-index: 2147483000; border: 0; border-radius: 22px; padding: 10px 18px; background: #0A3D2F; color: #fff; font-weight: 600; cursor: pointer; box-shadow: 0 6px 24px rgba(10,61,47,.3); }
    .panel { position: fixed; right: 20px; bottom: 72px; z-index: 2147483000; width: min(360px, calc(100vw - 32px)); background: #fff; color: #12261E; border: 1px solid #DFE8E2; border-radius: 14px; padding: 16px; box-shadow: 0 12px 40px rgba(10,61,47,.22); }
    h2 { margin: 0 0 10px; font-size: 16px; font-weight: 600; }
    input[type=text], textarea { width: 100%; border: 1.5px solid #C4D2C9; border-radius: 10px; padding: 8px 10px; margin: 0 0 8px; background: #fff; color: inherit; }
    textarea { min-height: 96px; resize: vertical; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    button.send { border: 0; border-radius: 8px; padding: 8px 14px; background: #2C6E24; color: #fff; font-weight: 600; cursor: pointer; }
    button.send:disabled { opacity: .5; cursor: not-allowed; }
    .msg { font-size: 12.5px; color: #5B7166; margin-top: 8px; }
    #mine { margin-top: 12px; border-top: 1px solid #DFE8E2; max-height: 260px; overflow-y: auto; }
    details { border-bottom: 1px solid #EEF4F0; padding: 6px 0; }
    summary { cursor: pointer; font-size: 13px; }
    .st { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: #317A28; margin-left: 6px; }
    .say { font-size: 12.5px; white-space: pre-wrap; margin: 6px 0; } .say b { font-weight: 600; }
    [hidden] { display: none !important; }
  </style>
  <button class="fab" part="button">${label.replace(/[<>&"]/g, '')}</button>
  <div class="panel" hidden role="dialog" aria-label="Contact support">
    <h2>Contact support</h2>
    <input type="text" id="t" placeholder="What is it about?" maxlength="200" aria-label="Title">
    <textarea id="d" placeholder="What happened, and what did you expect?" aria-label="Description"></textarea>
    <div class="row"><input type="file" id="f" accept="image/*" multiple aria-label="Screenshots"></div>
    <div class="row" style="margin-top:10px"><button class="send" id="s">Send</button></div>
    <div class="msg" id="m"></div>
    <div id="mine"></div>
  </div>`;
  const $ = s => root.querySelector(s);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const STL = { new: 'received', open: 'with support', waiting_on_customer: 'needs your answer', escalated: 'with the product team', resolved: 'answered', closed: 'closed' };
  const post = (path, body) => call(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  async function mine() {
    let rows; try { rows = await call('api/tickets?full=true', {}); } catch (e) { return; }
    $('#mine').innerHTML = rows.map(t => `<details><summary>${esc(t.key)} · ${esc(t.title)}<span class="st">${STL[t.status] || esc(t.status)}</span></summary>
      ${t.messages.map(m => `<div class="say"><b>${esc(m.by)}</b>: ${esc(m.text)}</div>`).join('')}
      ${t.status === 'closed' ? '' : `<textarea data-k="${esc(t.key)}" placeholder="Reply…" style="min-height:56px"></textarea>
      <div class="row"><button class="send" data-reply="${esc(t.key)}">Reply</button>${t.status === 'resolved' ? `<button class="send" data-close="${esc(t.key)}">Confirm it is solved</button>` : ''}</div>`}</details>`).join('');
  }
  $('#mine').addEventListener('click', async e => {
    const r = e.target.closest('[data-reply]'), c = e.target.closest('[data-close]');
    try {
      if (r) { const text = $(`textarea[data-k="${r.dataset.reply}"]`).value.trim(); if (!text) return; await post(`api/tickets/${r.dataset.reply}/messages`, { text }); }
      if (c) await post(`api/tickets/${c.dataset.close}/transition`, { to: 'closed' });
      if (r || c) mine();
    } catch (err) { $('#m').textContent = err.message; }
  });
  $('.fab').onclick = () => { $('.panel').hidden = !$('.panel').hidden; if (!$('.panel').hidden) { $('#t').focus(); mine(); } };
  $('#s').onclick = async () => {
    const title = $('#t').value.trim();
    if (title.length < 3) { $('#m').textContent = 'A short title, please.'; return; }
    $('#s').disabled = true; $('#m').textContent = 'Sending…';
    try {
      const screenshots = [];
      for (const file of $('#f').files) {
        const fd = new FormData(); fd.append('file', file, file.name);
        screenshots.push((await call('api/uploads', { method: 'POST', body: fd })).id);
      }
      const t = await post('api/tickets', { title, description: $('#d').value.trim(), screenshots,
        context: { pageUrl: location.href, appVersion, userAgent: navigator.userAgent } });
      $('#t').value = ''; $('#d').value = ''; $('#f').value = '';
      $('#m').textContent = `Thanks — ${t.key} is with the support team. Replies appear below.`;
      mine();
    } catch (e) { $('#m').textContent = 'Could not send: ' + e.message; }
    $('#s').disabled = false;
  };
  (document.body || document.documentElement).appendChild(host);
})();
