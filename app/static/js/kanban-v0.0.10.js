(() => {
  const root = document.querySelector('[data-kanban-root]');
  if (!root) return;
  const csrf = root.dataset.csrfToken || '';
  const funnelId = root.dataset.funnelId || '';
  let dragged = null;
  let moving = false;

  function toast(message, kind = 'error') {
    let el = document.querySelector('.kanban-toast');
    if (!el) {
      el = document.createElement('div');
      el.className = 'kanban-toast';
      document.body.appendChild(el);
    }
    el.className = `kanban-toast is-${kind}`;
    el.textContent = message;
    window.clearTimeout(el._timer);
    el._timer = window.setTimeout(() => el.remove(), 4200);
  }

  async function move(card, stageId) {
    if (!card || moving || card.dataset.stageId === stageId) return;
    moving = true;
    root.classList.add('is-moving');
    const body = new URLSearchParams({
      stage_id: stageId,
      lock_version: card.dataset.lockVersion || '0',
      csrf_token: csrf,
      response_mode: 'json',
      funnel_id: funnelId,
    });
    try {
      const response = await fetch(`/atendimentos/funil/oportunidades/${encodeURIComponent(card.dataset.opportunityId)}/mover`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        if (response.status === 409) {
          toast(data.error || 'A oportunidade foi alterada por outra ação. Recarregando o quadro.');
          window.setTimeout(() => window.location.reload(), 900);
          return;
        }
        throw new Error(data.error || `Não foi possível mover a oportunidade (HTTP ${response.status}).`);
      }
      card.dataset.stageId = data.opportunity.stage_id;
      card.dataset.lockVersion = String(data.opportunity.lock_version);
      window.location.reload();
    } catch (error) {
      toast(error.message || 'Não foi possível mover a oportunidade.');
    } finally {
      moving = false;
      root.classList.remove('is-moving');
    }
  }

  root.querySelectorAll('.kanban-card[draggable="true"]').forEach((card) => {
    card.addEventListener('dragstart', (event) => {
      dragged = card;
      card.classList.add('is-dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', card.dataset.opportunityId || '');
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('is-dragging');
      root.querySelectorAll('.kanban-dropzone.is-over').forEach((zone) => zone.classList.remove('is-over'));
      dragged = null;
    });
  });


  root.querySelectorAll('.kanban-card-delete-zone').forEach((zone) => {
    zone.addEventListener('mousedown', (event) => event.stopPropagation());
    zone.addEventListener('click', (event) => event.stopPropagation());
    zone.addEventListener('dragstart', (event) => {
      event.preventDefault();
      event.stopPropagation();
    });
  });

  root.querySelectorAll('[data-dropzone]').forEach((zone) => {
    zone.addEventListener('dragover', (event) => {
      if (!dragged) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      zone.classList.add('is-over');
    });
    zone.addEventListener('dragleave', (event) => {
      if (!zone.contains(event.relatedTarget)) zone.classList.remove('is-over');
    });
    zone.addEventListener('drop', (event) => {
      event.preventDefault();
      zone.classList.remove('is-over');
      if (!dragged) return;
      move(dragged, zone.dataset.stageId || '');
    });
  });
})();
