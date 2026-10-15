(() => {
  const root = document.querySelector('[data-kanban-root]');
  if (!root) return;

  const board = root.querySelector('[data-kanban-board]');
  if (!board) return;

  const csrf = root.dataset.csrfToken || '';
  const funnelId = root.dataset.funnelId || '';
  const search = root.dataset.search || '';
  const assignedUserId = root.dataset.assignedUser || '';
  const pollSeconds = Math.max(2, Number(root.dataset.pollSeconds || 4));
  const liveBadge = document.querySelector('#kanbanLiveBadge');

  let signature = root.dataset.kanbanSignature || '';
  let dragged = null;
  let moving = false;
  let polling = false;

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

  function setLiveState(ok) {
    if (!liveBadge) return;
    liveBadge.classList.toggle('is-offline', !ok);
    liveBadge.title = ok
      ? 'O funil é atualizado automaticamente'
      : 'Falha temporária ao atualizar o funil. O VENDRA continuará tentando.';
  }

  function feedUrl() {
    const params = new URLSearchParams();
    if (funnelId) params.set('funil', funnelId);
    if (search) params.set('q', search);
    if (assignedUserId) params.set('responsavel', assignedUserId);
    return `/atendimentos/funil/feed.json?${params.toString()}`;
  }

  function cardStageSnapshot() {
    const result = new Map();
    board.querySelectorAll('.kanban-card').forEach((card) => {
      result.set(card.dataset.opportunityId || '', card.dataset.stageId || '');
    });
    return result;
  }

  function markLiveChanges(before) {
    if (!before || !before.size) return;
    board.querySelectorAll('.kanban-card').forEach((card) => {
      const id = card.dataset.opportunityId || '';
      const oldStage = before.get(id);
      if (oldStage !== undefined && oldStage !== (card.dataset.stageId || '')) {
        card.classList.add('is-live-updated');
        window.setTimeout(() => card.classList.remove('is-live-updated'), 1600);
      }
      if (oldStage === undefined) {
        card.classList.add('is-live-updated');
        window.setTimeout(() => card.classList.remove('is-live-updated'), 1600);
      }
    });
  }

  function applyBoardHtml(html) {
    const scrollLeft = board.scrollLeft;
    const before = cardStageSnapshot();
    board.innerHTML = html || '';
    board.scrollLeft = scrollLeft;
    bindInteractions();
    markLiveChanges(before);
  }

  async function poll({ force = false } = {}) {
    if (polling || moving || dragged || document.visibilityState === 'hidden') return;
    polling = true;
    try {
      const response = await fetch(feedUrl(), {
        headers: { Accept: 'application/json' },
        cache: 'no-store',
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.empty) {
        if (force || signature !== data.signature) applyBoardHtml('');
        signature = data.signature || '';
        setLiveState(true);
        return;
      }
      if (force || signature !== data.signature) {
        applyBoardHtml(data.html || '');
        signature = data.signature || '';
        root.dataset.kanbanSignature = signature;
      }
      setLiveState(true);
    } catch (error) {
      setLiveState(false);
    } finally {
      polling = false;
    }
  }

  async function move(card, stageId) {
    if (!card || moving || !stageId || card.dataset.stageId === stageId) return;
    moving = true;
    root.classList.add('is-moving');
    const body = new URLSearchParams({
      stage_id: stageId,
      lock_version: card.dataset.lockVersion || '0',
      csrf_token: csrf,
      response_mode: 'json',
      funnel_id: funnelId,
      q: search,
      assigned_user_id: assignedUserId,
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
          toast(data.error || 'A oportunidade foi alterada por outra ação. Sincronizando o quadro.');
          return;
        }
        throw new Error(data.error || `Não foi possível mover a oportunidade (HTTP ${response.status}).`);
      }
      card.dataset.stageId = data.opportunity.stage_id;
      card.dataset.lockVersion = String(data.opportunity.lock_version);
      await poll({ force: true });
    } catch (error) {
      toast(error.message || 'Não foi possível mover a oportunidade.');
    } finally {
      moving = false;
      root.classList.remove('is-moving');
      // Reconcilia depois do desbloqueio para também cobrir conflito ou mudança concorrente.
      window.setTimeout(() => poll({ force: true }), 0);
    }
  }

  function bindInteractions() {
    board.querySelectorAll('.kanban-card[draggable="true"]').forEach((card) => {
      card.addEventListener('dragstart', (event) => {
        dragged = card;
        card.classList.add('is-dragging');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', card.dataset.opportunityId || '');
      });
      card.addEventListener('dragend', () => {
        card.classList.remove('is-dragging');
        board.querySelectorAll('.kanban-dropzone.is-over').forEach((zone) => zone.classList.remove('is-over'));
        dragged = null;
      });
    });

    board.querySelectorAll('.kanban-card-delete-zone').forEach((zone) => {
      zone.addEventListener('mousedown', (event) => event.stopPropagation());
      zone.addEventListener('click', (event) => event.stopPropagation());
      zone.addEventListener('dragstart', (event) => {
        event.preventDefault();
        event.stopPropagation();
      });
    });

    board.querySelectorAll('[data-dropzone]').forEach((zone) => {
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

    board.querySelectorAll('.kanban-mobile-move').forEach((form) => {
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        const card = form.closest('.kanban-card');
        const select = form.querySelector('[name="stage_id"]');
        move(card, select?.value || '');
      });
    });
  }

  bindInteractions();
  window.setInterval(() => poll(), pollSeconds * 1000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') poll({ force: true });
  });
  // Primeiro ciclo confirma o estado atual sem exigir recarga manual.
  poll();
})();
