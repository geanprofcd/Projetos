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
  const newMessageIndicator = document.querySelector('#newMessageIndicator');
  const whatsappWindowBar = document.querySelector('#whatsappWindowBar');
  const whatsappWindowTitle = document.querySelector('#whatsappWindowTitle');
  const whatsappWindowText = document.querySelector('#whatsappWindowText');
  const whatsappWindowCountdown = document.querySelector('#whatsappWindowCountdown');
  const maxFiles = 6;
  const maxBytes = Math.max(1, Number(root.dataset.attachmentMaxMb || 15)) * 1024 * 1024;
  const videoMaxBytes = Math.max(1, Number(root.dataset.videoMaxMb || 50)) * 1024 * 1024;
  const videoExtensions = new Set(['.mp4','.mov','.webm','.m4v','.3gp','.3g2','.avi','.mkv','.mpeg','.mpg','.wmv','.asf','.ogv','.flv','.ts','.mts','.m2ts','.vob']);
  let lastSignature = null;
  let polling = false;

  function setLiveState(ok) {
    if (!liveBadge) return;
    liveBadge.classList.toggle('is-offline', !ok);
    liveBadge.title = ok
      ? 'A conversa verifica novas mensagens automaticamente'
      : 'Sem atualização automática no momento. A página continuará tentando.';
  }

  function isNearMessageBottom(threshold = 96) {
    if (!messageList) return true;
    return messageList.scrollHeight - messageList.scrollTop - messageList.clientHeight <= threshold;
  }

  function scrollMessagesToBottom({ behavior = 'auto' } = {}) {
    if (!messageList) return;
    messageList.scrollTo({ top: messageList.scrollHeight, behavior });
    if (newMessageIndicator) newMessageIndicator.hidden = true;
  }

  function showNewMessageIndicator() {
    if (newMessageIndicator) newMessageIndicator.hidden = false;
  }

  function remainingLabel(seconds) {
    const safe = Math.max(0, Math.floor(seconds));
    const hours = Math.floor(safe / 3600);
    const minutes = Math.floor((safe % 3600) / 60);
    return hours > 0 ? `${hours}h ${String(minutes).padStart(2, '0')}min` : `${minutes}min`;
  }

  function applyWindowVisual(state) {
    if (!whatsappWindowBar || !state) return;
    const open = Boolean(state.open);
    root.dataset.windowOpen = open ? 'true' : 'false';
    root.dataset.windowExpiresAt = state.expires_at || '';
    whatsappWindowBar.dataset.expiresAt = state.expires_at || '';
    whatsappWindowBar.classList.toggle('is-open', open);
    whatsappWindowBar.classList.toggle('is-closed', !open);
    if (whatsappWindowTitle) whatsappWindowTitle.textContent = open ? 'Janela WhatsApp aberta' : 'Janela WhatsApp encerrada';
    if (whatsappWindowText) {
      if (open) {
        const remaining = remainingLabel(Number(state.remaining_seconds || 0));
        whatsappWindowText.textContent = `Mensagens livres estão permitidas. Tempo restante: ${remaining}.`;
      } else {
        whatsappWindowText.textContent = 'Mensagens livres estão bloqueadas. Para iniciar ou retomar o contato, use um modelo aprovado da Meta.';
      }
    }
  }

  function tickWhatsappWindow() {
    if (!whatsappWindowBar) return;
    const expiresAt = root.dataset.windowExpiresAt || whatsappWindowBar.dataset.expiresAt || '';
    if (!expiresAt || root.dataset.windowOpen !== 'true') return;
    const remaining = Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000);
    if (remaining <= 0) {
      applyWindowVisual({ open: false, expires_at: expiresAt, remaining_seconds: 0 });
      return;
    }
    if (whatsappWindowCountdown) whatsappWindowCountdown.textContent = remainingLabel(remaining);
    else if (whatsappWindowText) whatsappWindowText.textContent = `Mensagens livres estão permitidas. Tempo restante: ${remainingLabel(remaining)}.`;
  }

  function attachmentNode(item) {
    if (item.is_audio) {
      const card = document.createElement('div');
      card.className = 'attachment-media-card audio';
      const head = document.createElement('div');
      head.className = 'attachment-media-head';
      const icon = document.createElement('span');
      icon.className = 'attachment-icon';
      icon.textContent = '♪';
      const info = document.createElement('span');
      info.className = 'attachment-info';
      const strong = document.createElement('strong');
      strong.textContent = item.file_name;
      const small = document.createElement('small');
      small.textContent = `${item.size_label || ''}${item.size_label ? ' · ' : ''}áudio`;
      info.append(strong, small);
      head.append(icon, info);
      const player = document.createElement('audio');
      player.controls = true;
      player.preload = 'metadata';
      player.src = item.url;
      const download = document.createElement('a');
      download.className = 'attachment-download';
      download.href = item.url;
      download.target = '_blank';
      download.rel = 'noopener';
      download.textContent = 'Abrir / baixar arquivo';
      card.append(head, player, download);
      return card;
    }

    if (item.is_video && item.is_browser_playable_video) {
      const card = document.createElement('div');
      card.className = 'attachment-media-card video';
      const player = document.createElement('video');
      player.controls = true;
      player.preload = 'metadata';
      player.playsInline = true;
      player.src = item.url;
      const head = document.createElement('div');
      head.className = 'attachment-media-head';
      const icon = document.createElement('span');
      icon.className = 'attachment-icon';
      icon.textContent = '▶';
      const info = document.createElement('span');
      info.className = 'attachment-info';
      const strong = document.createElement('strong');
      strong.textContent = item.file_name;
      const small = document.createElement('small');
      small.textContent = `${item.size_label || ''}${item.size_label ? ' · ' : ''}vídeo`;
      info.append(strong, small);
      head.append(icon, info);
      const download = document.createElement('a');
      download.className = 'attachment-download';
      download.href = item.url;
      download.target = '_blank';
      download.rel = 'noopener';
      download.textContent = 'Abrir / baixar arquivo';
      card.append(player, head, download);
      return card;
    }

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
    icon.textContent = item.is_pdf ? 'PDF' : (item.is_video ? 'VID' : '↗');
    const info = document.createElement('span');
    info.className = 'attachment-info';
    const strong = document.createElement('strong');
    strong.textContent = item.file_name;
    const small = document.createElement('small');
    const action = item.is_video ? 'formato salvo; abrir/baixar' : 'abrir arquivo';
    small.textContent = `${item.size_label || ''}${item.size_label ? ' · ' : ''}${action}`;
    info.append(strong, small);
    link.append(icon, info);
    return link;
  }

  function deliveryLabel(status) {
    if (status === 'read') return 'Lido';
    if (status === 'sent' || status === 'delivered') return 'Enviado';
    if (status === 'failed') return 'Falha no envio';
    return '';
  }

  function applyDeliveryContent(node, message) {
    const label = deliveryLabel(message.delivery_status);
    node.replaceChildren();
    node.append(document.createTextNode(label));
    if (message.delivery_status === 'failed' && message.delivery_error) {
      const error = document.createElement('span');
      error.className = 'message-delivery-error';
      error.textContent = message.delivery_error;
      node.appendChild(error);
    }
  }

  function messageNode(message) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message';
    if (message.mine) wrapper.classList.add('mine');
    if (message.is_internal) wrapper.classList.add('internal');
    wrapper.dataset.messageId = message.id;

    const author = document.createElement('div');
    author.className = 'message-author';
    author.textContent = `${message.sender_kind === 'ai' ? 'Assistente de IA' : message.sender_name}${message.is_internal ? ' · nota interna' : ''}`;
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

    const initialDeliveryLabel = deliveryLabel(message.delivery_status);
    if (message.mine && initialDeliveryLabel) {
      const delivery = document.createElement('div');
      delivery.className = `message-delivery is-${message.delivery_status}`;
      delivery.dataset.deliveryStatus = message.delivery_status;
      applyDeliveryContent(delivery, message);
      wrapper.appendChild(delivery);
    }
    return wrapper;
  }

  function syncMessages(messages) {
    if (!messageList || !endMarker) return;
    const shouldFollow = isNearMessageBottom();
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
      const label = deliveryLabel(message.delivery_status);
      if (label) {
        if (oldDelivery) {
          oldDelivery.className = `message-delivery is-${message.delivery_status}`;
          oldDelivery.dataset.deliveryStatus = message.delivery_status;
          applyDeliveryContent(oldDelivery, message);
        } else {
          const delivery = document.createElement('div');
          delivery.className = `message-delivery is-${message.delivery_status}`;
          delivery.dataset.deliveryStatus = message.delivery_status;
          applyDeliveryContent(delivery, message);
          current.appendChild(delivery);
        }
      } else if (oldDelivery) {
        oldDelivery.remove();
      }
    });
    if (!appended || document.visibilityState !== 'visible') return;
    if (shouldFollow) {
      scrollMessagesToBottom({ behavior: 'smooth' });
    } else {
      showNewMessageIndicator();
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
        if (data.whatsapp_window) applyWindowVisual(data.whatsapp_window);
        const controlBar = document.getElementById('aiControlBar');
        if (controlBar && data.automation && String(data.automation.control_version || '') !== String(controlBar.dataset.controlVersion || '')) {
          window.location.reload();
          return;
        }
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
    if (root.dataset.windowOpen === 'false') {
      event.preventDefault();
      alert('A janela de 24 horas do WhatsApp está encerrada. Use Disparos com um modelo aprovado.');
      return;
    }
    const files = [...(fileInput?.files || [])];
    if (files.length > maxFiles) {
      event.preventDefault();
      alert(`Envie no máximo ${maxFiles} arquivos por mensagem.`);
      return;
    }
    const oversized = files.find((file) => {
      const lower = file.name.toLowerCase();
      const dot = lower.lastIndexOf('.');
      const ext = dot >= 0 ? lower.slice(dot) : '';
      const limit = videoExtensions.has(ext) ? videoMaxBytes : maxBytes;
      return file.size > limit;
    });
    if (oversized) {
      event.preventDefault();
      const lower = oversized.name.toLowerCase();
      const dot = lower.lastIndexOf('.');
      const ext = dot >= 0 ? lower.slice(dot) : '';
      const limitMb = videoExtensions.has(ext) ? Math.round(videoMaxBytes / 1024 / 1024) : Math.round(maxBytes / 1024 / 1024);
      alert(`O arquivo “${oversized.name}” excede ${limitMb} MB.`);
    }
  });

  messageList?.addEventListener('scroll', () => {
    if (isNearMessageBottom()) {
      if (newMessageIndicator) newMessageIndicator.hidden = true;
    }
  }, { passive: true });
  newMessageIndicator?.addEventListener('click', () => scrollMessagesToBottom({ behavior: 'smooth' }));

  // A rolagem inicial acontece apenas dentro da conversa — nunca na página inteira.
  window.requestAnimationFrame(() => scrollMessagesToBottom({ behavior: 'auto' }));
  tickWhatsappWindow();
  window.setInterval(tickWhatsappWindow, 60 * 1000);
  window.setInterval(poll, pollSeconds * 1000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      tickWhatsappWindow();
      poll();
    }
  });
  poll();
})();
