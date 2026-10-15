/* VENDRA 0.0.25 — notificações transitórias de SLA: 5s + fade, fechamento manual.
 * A pendência segue disponível no menu, mesmo que o pop-up seja dispensado. */
(() => {
  const root = document.querySelector('[data-lead-alert-root]');
  if (!root) return;
  const countEl = root.querySelector('[data-alert-count]');
  const listEl = root.querySelector('[data-alert-list]');
  const statusEl = root.querySelector('[data-alert-status]');
  const dismissBtn = root.querySelector('[data-alert-dismiss]');
  const openBtn = document.querySelector('[data-alert-open]');
  const openLabel = document.querySelector('[data-alert-open-label]');
  const soundButtons = [...document.querySelectorAll('[data-alert-sound]')];
  const enableKey = 'vendra:lead-alert:sound-enabled';
  const notifiedKey = 'vendra:lead-alert:notified';
  let soundEnabled = localStorage.getItem(enableKey) === 'yes';
  let notified;
  try {
    const restored = JSON.parse(sessionStorage.getItem(notifiedKey) || '[]');
    notified = new Set(Array.isArray(restored) ? restored.filter((key) => typeof key === 'string') : []);
  } catch (_error) {
    notified = new Set();
  }
  let alerts = [];
  let audioContext = null;
  let polling = false;
  let dismissTimer = null;
  let fadeTimer = null;

  function formatWait(minutes) {
    const n = Math.max(0, Math.floor(Number(minutes) || 0));
    const hours = String(Math.floor(n / 60)).padStart(2, '0');
    const mins = String(n % 60).padStart(2, '0');
    return `${hours}h ${mins}min`;
  }
  function stopTimers() {
    clearTimeout(dismissTimer);
    clearTimeout(fadeTimer);
    dismissTimer = null;
    fadeTimer = null;
  }
  function hidePopup(fade = false) {
    stopTimers();
    if (root.hidden) return;
    if (fade) {
      root.classList.add('is-fading');
      fadeTimer = setTimeout(() => {
        root.hidden = true;
        root.classList.remove('is-fading');
        fadeTimer = null;
      }, 650);
    } else {
      root.hidden = true;
      root.classList.remove('is-fading');
    }
  }
  function showPopup() {
    if (!alerts.length) return;
    stopTimers();
    root.classList.remove('is-fading');
    root.hidden = false;
    // Após cinco segundos VISÍVEL, o cartão inicia a transição de saída.
    dismissTimer = setTimeout(() => hidePopup(true), 5000);
  }
  dismissBtn?.addEventListener('click', () => {
    hidePopup();
    if (openBtn && !openBtn.hidden) openBtn.focus();
  });
  openBtn?.addEventListener('click', showPopup);

  function updateSoundButton() {
    soundButtons.forEach((btn) => {
      const footer = btn.classList.contains('lead-alert-sidebar-sound');
      btn.textContent = soundEnabled ? (footer ? '🔔 Som dos alertas ligado' : 'Som ligado') : (footer ? '🔕 Ativar som dos alertas' : 'Ativar som');
      btn.setAttribute('aria-pressed', String(soundEnabled));
      btn.title = soundEnabled ? 'Desativar alerta sonoro' : 'Ativar alerta sonoro neste navegador';
    });
  }
  async function unlockAudio() {
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return false;
    audioContext ||= new Audio();
    await audioContext.resume();
    return audioContext.state === 'running';
  }
  function beep() {
    if (!soundEnabled || !audioContext || audioContext.state !== 'running') return;
    const t = audioContext.currentTime;
    [0, 0.2].forEach((offset) => {
      const osc = audioContext.createOscillator();
      const gain = audioContext.createGain();
      osc.type = 'sine';
      osc.frequency.value = 740;
      gain.gain.setValueAtTime(0.0001, t + offset);
      gain.gain.exponentialRampToValueAtTime(0.16, t + offset + 0.025);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + offset + 0.16);
      osc.connect(gain); gain.connect(audioContext.destination);
      osc.start(t + offset); osc.stop(t + offset + 0.18);
    });
  }
  soundButtons.forEach((btn) => btn.addEventListener('click', async () => {
    if (soundEnabled) {
      soundEnabled = false;
    } else {
      soundEnabled = await unlockAudio();
      if (!soundEnabled) statusEl.textContent = 'O navegador não liberou o áudio. Clique novamente.';
    }
    localStorage.setItem(enableKey, soundEnabled ? 'yes' : 'no');
    updateSoundButton();
  }));
  updateSoundButton();
  // Navegador: o áudio só pode ser desbloqueado após interação do operador.
  if (soundEnabled) document.addEventListener('pointerdown', () => { unlockAudio().catch(() => {}); }, {once: true});

  function render(items) {
    alerts = Array.isArray(items) ? items : [];
    const validKeys = new Set(alerts.map((alert) => alert.key));
    notified = new Set([...notified].filter((key) => validKeys.has(key)));
    const fresh = alerts.filter((alert) => !notified.has(alert.key));
    alerts.forEach((alert) => notified.add(alert.key));
    sessionStorage.setItem(notifiedKey, JSON.stringify([...notified].slice(-200)));

    countEl.textContent = String(alerts.length);
    statusEl.textContent = `${alerts.length} conversa(s) aguardando resposta há mais de 30 minutos`;
    if (openBtn) {
      openBtn.hidden = alerts.length === 0;
      openBtn.setAttribute('aria-label', `${alerts.length} atendimento(s) em atraso. Abrir avisos`);
    }
    if (openLabel) openLabel.textContent = `Atrasos: ${alerts.length}`;
    listEl.replaceChildren();
    alerts.forEach((alert) => {
      const link = document.createElement('a');
      link.className = 'lead-alert-item';
      link.href = `/atendimentos/${encodeURIComponent(alert.ticket_id)}`;
      const name = document.createElement('strong');
      name.textContent = alert.customer_name;
      const wait = document.createElement('span');
      wait.textContent = `Sem resposta há ${formatWait(alert.minutes)}`;
      link.append(name, wait);
      listEl.append(link);
    });
    const pendingTickets = new Set(alerts.map((alert) => String(alert.ticket_id)));
    document.querySelectorAll('[data-ticket-alert-id]').forEach((element) => {
      element.classList.toggle('is-sla-overdue', pendingTickets.has(element.dataset.ticketAlertId));
    });
    if (!alerts.length) hidePopup();
    else if (fresh.length) {
      showPopup();
      beep();
    }
    // Se não houve novo atraso, o polling NÃO abre novamente um aviso fechado.
  }
  async function poll() {
    if (polling || document.visibilityState !== 'visible') return;
    polling = true;
    try {
      const response = await fetch('/atendimentos/alertas.json', {
        credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}
      });
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const result = await response.json();
      render(result.alerts || []);
    } catch (_error) {
      // Falha de rede não deve limpar nem recriar alertas já notificados.
      if (!root.hidden) statusEl.textContent = 'Falha ao atualizar os alertas. Tentaremos novamente.';
    } finally { polling = false; }
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') poll();
  });
  window.addEventListener('focus', poll);
  setInterval(poll, 15000);
  poll();
})();
