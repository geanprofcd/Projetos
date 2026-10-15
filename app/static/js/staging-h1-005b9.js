/* H1-005B9 — Resultado transientemente em DOM. Nenhum storage/cookie/URL com mensagem. */
(() => {
  "use strict";
  const form = document.getElementById('vendra-b9-preflight-form');
  const card = document.getElementById('vendra-b9-result');
  const error = document.getElementById('vendra-b9-error');
  if (!form || !card || !error || !window.fetch) return;
  const allowed = ["opportunity_title", "customer_name", "phone_masked",
    "rendered_message", "idempotency_reference", "destination", "delivery_state"];
  const button = form.querySelector('button[type="submit"]');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    card.hidden = true;
    error.hidden = true;
    if (button) button.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Accept': 'application/json' },
        body: new FormData(form), redirect: 'error', cache: 'no-store'
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok || !payload.plan) {
        throw new Error(typeof payload.error === 'string' ? payload.error : 'Validacao recusada.');
      }
      for (const key of allowed) {
        const node = card.querySelector('[data-key="' + key + '"]');
        if (node) node.textContent = String(payload.plan[key] ?? '');
      }
      card.hidden = false;
      card.scrollIntoView({behavior:'smooth',block:'nearest'});
    } catch (ex) {
      error.textContent = ex instanceof Error ? ex.message : 'Preflight indisponivel.';
      error.hidden = false;
    } finally {
      if (button) button.disabled = false;
    }
  });
})();
