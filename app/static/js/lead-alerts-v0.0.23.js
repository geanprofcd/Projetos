(() => {
  const root = document.querySelector('[data-lead-alert-root]');
  if (!root) return;
  const countEl = root.querySelector('[data-alert-count]');
  const listEl = root.querySelector('[data-alert-list]');
  const soundButtons = [...document.querySelectorAll('[data-alert-sound]')];
  const statusEl = root.querySelector('[data-alert-status]');
  const enableKey = 'vendra:lead-alert:sound-enabled';
  const notifiedKey = 'vendra:lead-alert:notified';
  let soundEnabled = localStorage.getItem(enableKey) === 'yes';
  let notified = new Set(JSON.parse(sessionStorage.getItem(notifiedKey) || '[]'));
  let audioContext = null;
  let polling = false;

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
  soundButtons.forEach((soundBtn) => soundBtn.addEventListener('click', async () => {
    if (soundEnabled) {
      soundEnabled = false;
    } else {
      soundEnabled = await unlockAudio();
      if (!soundEnabled) statusEl.textContent = 'O navegador não liberou o áudio. Clique novamente.';
    }
    localStorage.setItem(enableKey, soundEnabled ? 'yes' : 'no');
    updateSoundButton();
    if (soundEnabled && !root.hidden) beep();
  }));
  updateSoundButton();
  // O navegador exige gesto do usuário a cada novo contexto de áudio.
  if (soundEnabled) document.addEventListener('pointerdown', () => { unlockAudio().catch(() => {}); }, {once: true});

  function render(alerts) {
    const visibleKeys = new Set(alerts.map((a) => a.key));
    // Evita repetir som após navegar entre telas, mas permite nova pendência.
    notified = new Set([...notified].filter((key) => visibleKeys.has(key)));
    const fresh = alerts.filter((alert) => !notified.has(alert.key));
    alerts.forEach((a) => notified.add(a.key));
    sessionStorage.setItem(notifiedKey, JSON.stringify([...notified].slice(-200)));
    root.hidden = alerts.length === 0;
    countEl.textContent = String(alerts.length);
    statusEl.textContent = `${alerts.length} conversa(s) aguardando há mais de 30 minutos`;
    listEl.replaceChildren();
    alerts.forEach((alert) => {
      const link = document.createElement('a');
      link.className = 'lead-alert-item';
      link.href = `/atendimentos/${encodeURIComponent(alert.ticket_id)}`;
      const name = document.createElement('strong');
      name.textContent = alert.customer_name;
      const detail = document.createElement('span');
      detail.textContent = `Sem resposta há ${alert.minutes} min · ${alert.first_reply_time || '—'}`;
      link.append(name, detail);
      listEl.append(link);
    });
    document.querySelectorAll('[data-ticket-alert-id]').forEach((element) => {
      element.classList.toggle('is-sla-overdue', alerts.some((alert) => alert.ticket_id === element.dataset.ticketAlertId));
    });
    if (fresh.length) beep();
  }
  async function poll() {
    if (polling || document.visibilityState !== 'visible') return;
    polling = true;
    try {
      const response = await fetch('/atendimentos/alertas.json', {credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}});
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const result = await response.json();
      render(result.alerts || []);
    } catch (error) {
      statusEl.textContent = 'Falha ao verificar os alertas. Nova tentativa em breve.';
    } finally { polling = false; }
  }
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') poll(); });
  window.addEventListener('focus', poll);
  setInterval(poll, 15000);
  poll();
})();
