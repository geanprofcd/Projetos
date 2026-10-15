(() => {
  const root = document.querySelector('#ticketLiveRoot');
  if (!root) return;

  const ticketId = root.dataset.ticketId;
  const pollSeconds = Math.max(2, Number(root.dataset.pollSeconds || 4));
  const messageList = document.querySelector('#messagesList');
  const endMarker = document.querySelector('#fim');
  const liveBadge = document.querySelector('#liveBadge');
  const statusBadge = document.querySelector('#ticketStatusBadge');
  const fileInput = document.querySelector('#messageFiles');
  const selectedFiles = document.querySelector('#selectedFiles');
  const composer = document.querySelector('#messageComposer');
  const maxFiles = 6;
  const maxBytes = 15 * 1024 * 1024;
  let lastSignature = null;
  let polling = false;

  function setLiveState(ok) {
    if (!liveBadge) return;
    liveBadge.classList.toggle('is-offline', !ok);
    liveBadge.title = ok
      ? 'A conversa verifica novas mensagens automaticamente'
      : 'Sem atualização automática no momento. A página continuará tentando.';
  }

  function attachmentNode(item) {
    const link = document.createElement('a');
    link.href = item.url;
    link.target = '_blank';
    link.rel = 'noopener';
    link.title = `Abrir ${item.file_name}`;
    link.className = `attachment-card${item.is_image ? ' image' : ''}`;

    if (item.is_image) {
      const img = document.createElement('img');
      img.src = item.url;
      img.alt = item.file_name;
      img.loading = 'lazy';
      link.appendChild(img);

      const caption = document.createElement('span');
      caption.className = 'attachment-caption';
      const info = document.createElement('span');
      info.className = 'attachment-info';
      const strong = document.createElement('strong');
      strong.textContent = item.file_name;
      const small = document.createElement('small');
      small.textContent = item.size_label || '';
      info.append(strong, small);
      caption.appendChild(info);
      link.appendChild(caption);
      return link;
    }

    const icon = document.createElement('span');
    icon.className = 'attachment-icon';
    icon.textContent = item.is_pdf ? 'PDF' : '↗';
    const info = document.createElement('span');
    info.className = 'attachment-info';
    const strong = document.createElement('strong');
    strong.textContent = item.file_name;
    const small = document.createElement('small');
    small.textContent = `${item.size_label || ''}${item.size_label ? ' · ' : ''}abrir arquivo`;
    info.append(strong, small);
    link.append(icon, info);
    return link;
  }

  function messageNode(message) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message';
    if (message.mine) wrapper.classList.add('mine');
    if (message.is_internal) wrapper.classList.add('internal');
    wrapper.dataset.messageId = message.id;

    const author = document.createElement('div');
    author.className = 'message-author';
    author.textContent = `${message.sender_name}${message.is_internal ? ' · nota interna' : ''}`;
    wrapper.appendChild(author);

    if (message.body) {
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = message.body;
      wrapper.appendChild(bubble);
    }

    if (message.attachments && message.attachments.length) {
      const attachments = document.createElement('div');
      attachments.className = 'message-attachments';
      message.attachments.forEach((item) => attachments.appendChild(attachmentNode(item)));
      wrapper.appendChild(attachments);
    }

    if (message.mine && message.delivery_status) {
      const delivery = document.createElement('div');
      delivery.className = `message-delivery is-${message.delivery_status}`;
      delivery.dataset.deliveryStatus = message.delivery_status;
      delivery.textContent = `WhatsApp: ${message.delivery_status}`;
      wrapper.appendChild(delivery);
    }
    return wrapper;
  }

  function syncMessages(messages) {
    if (!messageList || !endMarker) return;
    const existing = new Set(
      [...messageList.querySelectorAll('[data-message-id]')].map((node) => node.dataset.messageId)
    );
    let appended = false;
    messages.forEach((message) => {
      if (!existing.has(message.id)) {
        const empty = document.querySelector('#emptyMessages');
        empty?.remove();
        messageList.insertBefore(messageNode(message), endMarker);
        appended = true;
        return;
      }
      const current = messageList.querySelector(`[data-message-id="${CSS.escape(message.id)}"]`);
      if (!current || !message.mine) return;
      const oldDelivery = current.querySelector('.message-delivery');
      if (message.delivery_status) {
        if (oldDelivery) {
          oldDelivery.className = `message-delivery is-${message.delivery_status}`;
          oldDelivery.dataset.deliveryStatus = message.delivery_status;
          oldDelivery.textContent = `WhatsApp: ${message.delivery_status}`;
        } else {
          const delivery = document.createElement('div');
          delivery.className = `message-delivery is-${message.delivery_status}`;
          delivery.dataset.deliveryStatus = message.delivery_status;
          delivery.textContent = `WhatsApp: ${message.delivery_status}`;
          current.appendChild(delivery);
        }
      }
    });
    if (appended && document.visibilityState === 'visible') {
      endMarker.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }

  function updateTicketState(ticket) {
    if (!statusBadge || !ticket?.status) return;
    statusBadge.className = `status status-${ticket.status}`;
    statusBadge.textContent = ticket.status.replaceAll('_', ' ');
  }

  async function poll() {
    if (polling || document.visibilityState === 'hidden') return;
    polling = true;
    try {
      const response = await fetch(`/atendimentos/${encodeURIComponent(ticketId)}/mensagens.json`, {
        headers: { Accept: 'application/json' },
        cache: 'no-store',
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (lastSignature === null || data.signature !== lastSignature) {
        syncMessages(data.messages || []);
        updateTicketState(data.ticket || {});
        lastSignature = data.signature;
      }
      setLiveState(true);
    } catch (error) {
      setLiveState(false);
    } finally {
      polling = false;
    }
  }

  function renderSelectedFiles() {
    if (!selectedFiles || !fileInput) return;
    selectedFiles.replaceChildren();
    const files = [...fileInput.files];
    files.slice(0, maxFiles).forEach((file) => {
      const chip = document.createElement('span');
      chip.className = 'selected-file';
      chip.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(file.size >= 1024 * 1024 ? 1 : 2)} MB`;
      selectedFiles.appendChild(chip);
    });
  }

  fileInput?.addEventListener('change', renderSelectedFiles);
  composer?.addEventListener('submit', (event) => {
    const files = [...(fileInput?.files || [])];
    if (files.length > maxFiles) {
      event.preventDefault();
      alert(`Envie no máximo ${maxFiles} arquivos por mensagem.`);
      return;
    }
    const oversized = files.find((file) => file.size > maxBytes);
    if (oversized) {
      event.preventDefault();
      alert(`O arquivo “${oversized.name}” excede 15 MB.`);
    }
  });

  window.setInterval(poll, pollSeconds * 1000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') poll();
  });
  poll();
})();
