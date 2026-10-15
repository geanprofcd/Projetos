(() => {
  const search = document.querySelector('#search');
  const statusFilter = document.querySelector('#statusFilter');
  const list = document.querySelector('#ticketList');
  const root = document.querySelector('#ticketsLiveRoot');
  const liveBadge = document.querySelector('#ticketsLiveBadge');
  if (!list || !root) return;

  const pollSeconds = Math.max(2, Number(root.dataset.pollSeconds || 4));
  let signature = null;
  let polling = false;

  function setLiveState(ok) {
    if (!liveBadge) return;
    liveBadge.classList.toggle('is-offline', !ok);
    liveBadge.title = ok ? 'A fila é atualizada automaticamente' : 'Falha temporária ao atualizar a fila';
  }

  function ticketRow(ticket) {
    const link = document.createElement('a');
    link.className = 'ticket-row';
    link.href = `/atendimentos/${encodeURIComponent(ticket.id)}`;
    link.dataset.status = ticket.status;
    link.dataset.search = `${ticket.customer_name} ${ticket.farm_name} ${ticket.title} ${ticket.crop_name}`;

    const avatar = document.createElement('div');
    avatar.className = 'ticket-avatar';
    avatar.textContent = (ticket.customer_name || 'C').trim().charAt(0).toUpperCase();

    const main = document.createElement('div');
    main.className = 'ticket-main';
    const line = document.createElement('div');
    line.className = 'ticket-line';
    const customer = document.createElement('strong');
    customer.textContent = ticket.customer_name;
    const id = document.createElement('span');
    id.textContent = `#${ticket.id}`;
    line.append(customer, id);
    const title = document.createElement('h3');
    title.textContent = ticket.title;
    const context = document.createElement('p');
    context.textContent = `${ticket.farm_name} · ${ticket.crop_name}`;
    main.append(line, title, context);

    const meta = document.createElement('div');
    meta.className = 'ticket-meta';
    const source = document.createElement('span');
    source.className = 'source';
    source.textContent = ticket.source;
    const status = document.createElement('span');
    status.className = `status status-${ticket.status}`;
    status.textContent = ticket.status.replaceAll('_', ' ');
    const responsible = document.createElement('small');
    responsible.textContent = ticket.assigned_name || 'Sem responsável';
    meta.append(source, status, responsible);

    link.append(avatar, main, meta);
    return link;
  }

  function applyFilters() {
    const q = (search?.value || '').toLowerCase().trim();
    const status = statusFilter?.value || '';
    const rows = [...list.querySelectorAll('.ticket-row')];
    rows.forEach((row) => {
      const matchesText = !q || (row.dataset.search || '').toLowerCase().includes(q);
      const matchesStatus = !status || row.dataset.status === status;
      row.style.display = matchesText && matchesStatus ? '' : 'none';
    });
  }

  function render(items) {
    list.replaceChildren();
    if (!items.length) {
      const empty = document.createElement('div');
      empty.className = 'ticket-list-empty';
      empty.textContent = 'Nenhum atendimento encontrado.';
      list.appendChild(empty);
      return;
    }
    items.forEach((ticket) => list.appendChild(ticketRow(ticket)));
    applyFilters();
  }

  async function poll() {
    if (polling || document.visibilityState === 'hidden') return;
    polling = true;
    try {
      const response = await fetch('/atendimentos/feed.json', {
        headers: { Accept: 'application/json' },
        cache: 'no-store',
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (signature === null || signature !== data.signature) {
        render(data.tickets || []);
        signature = data.signature;
      }
      setLiveState(true);
    } catch (error) {
      setLiveState(false);
    } finally {
      polling = false;
    }
  }

  search?.addEventListener('input', applyFilters);
  statusFilter?.addEventListener('change', applyFilters);
  window.setInterval(poll, pollSeconds * 1000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') poll();
  });
  poll();
})();
