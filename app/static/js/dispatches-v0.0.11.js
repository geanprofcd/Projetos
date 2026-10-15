(() => {
  const panel = document.querySelector('[data-bulk-panel]');
  if (!panel) return;

  const form = panel.querySelector('.dispatch-bulk-form');
  const button = panel.querySelector('.dispatch-all-button');
  const message = panel.querySelector('[data-bulk-message]');
  const progressWrap = panel.querySelector('.dispatch-bulk-progress');
  const progress = panel.querySelector('[data-bulk-progress]');
  const progressUrl = panel.dataset.progressUrl;

  if (form && button) {
    form.addEventListener('submit', (event) => {
      const count = Number(form.dataset.readyCount || '0');
      if (count <= 0) return;
      if (!window.confirm(`Enviar ${count} contato(s) um por vez para o Make?`)) {
        event.preventDefault();
        return;
      }
      button.disabled = true;
      button.textContent = 'Iniciando fila…';
    });
  }

  const active = () => ['queued', 'running'].includes(panel.dataset.bulkStatus || '');
  if (!active() || !progressUrl) return;

  const update = async () => {
    try {
      const response = await fetch(progressUrl, {headers: {'Accept': 'application/json'}, cache: 'no-store'});
      if (!response.ok) return;
      const state = await response.json();
      panel.dataset.bulkStatus = state.status || 'idle';
      if (progressWrap) progressWrap.hidden = !['queued', 'running'].includes(state.status);
      if (progress) progress.style.width = `${state.percent || 0}%`;
      if (message) {
        if (['queued', 'running'].includes(state.status)) {
          message.textContent = `Enviando ${state.processed || 0} de ${state.total || 0} contato(s), um por vez para o Make.`;
        } else if (state.status === 'completed') {
          message.textContent = `Fila concluída: ${state.processed || 0} contato(s) processados.`;
        } else if (state.status === 'completed_with_errors') {
          message.textContent = `Fila concluída com ${state.failed || 0} falha(s).`;
        } else if (state.status === 'interrupted') {
          message.textContent = state.last_error || 'A fila foi interrompida.';
        }
      }
      if (!['queued', 'running'].includes(state.status)) {
        window.setTimeout(() => window.location.reload(), 500);
        return;
      }
      window.setTimeout(update, 1200);
    } catch (_) {
      window.setTimeout(update, 2200);
    }
  };
  window.setTimeout(update, 650);
})();
