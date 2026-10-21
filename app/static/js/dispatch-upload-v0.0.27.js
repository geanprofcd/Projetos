(() => {
  const form = document.querySelector('[data-import-form]');
  if (!form) return;
  const input = form.querySelector('[type="file"]');
  const zone = form.querySelector('[data-import-zone]');
  const name = form.querySelector('[data-import-name]');
  const status = form.querySelector('[data-import-status]');
  const icon = form.querySelector('[data-import-icon]');
  const button = form.querySelector('[type="submit"]');
  if (!input || !zone || !name || !status || !icon || !button) return;
  const initial = {state: zone.dataset.importState, name: name.textContent, status: status.textContent, icon: icon.textContent};
  const buttonText = button.textContent;
  const disabledInitially = button.disabled;
  let busy = false;
  const show = (state, filename, message) => {
    zone.dataset.importState = state;
    zone.setAttribute('aria-busy', String(state === 'loading'));
    name.textContent = filename;
    status.textContent = message;
    icon.textContent = state === 'loading' ? '' : state === 'ready' ? '▤' : state === 'error' ? '!' : '↑';
  };
  const restoreControls = () => {
    busy = false;
    input.disabled = false;
    button.disabled = disabledInitially;
    button.textContent = buttonText;
  };
  input.addEventListener('change', () => {
    const file = input.files[0];
    if (!file) {
      show(initial.state, initial.name, initial.status);
      icon.textContent = initial.icon;
      return;
    }
    show('selected', file.name, 'Arquivo selecionado. Clique em “Importar e revisar” para carregar os contatos.');
  });
  form.addEventListener('submit', (event) => {
    if (busy || disabledInitially) { event.preventDefault(); return; }
    if (!input.files.length || !form.reportValidity()) return;
    event.preventDefault();
    const filename = input.files[0].name;
    const body = new FormData(form); // Capturar arquivo e CSRF antes de bloquear os controles.
    busy = true;
    input.disabled = true;
    button.disabled = true;
    button.textContent = 'Importando…';
    show('loading', filename, 'Carregando arquivo…');
    const request = new XMLHttpRequest();
    request.open('POST', form.action);
    const fail = (message) => {
      restoreControls();
      show('error', filename, message);
    };
    request.upload.addEventListener('progress', (progress) => {
      if (!busy) return;
      status.textContent = progress.lengthComputable && progress.loaded < progress.total
        ? `Carregando arquivo… ${Math.floor(progress.loaded / progress.total * 100)}%`
        : 'Arquivo recebido. Importando e validando os contatos…';
    });
    request.addEventListener('load', () => {
      const target = new URL(request.responseURL || form.action, window.location.href);
      if (target.origin === window.location.origin && target.pathname === '/login') {
        window.location.assign(target.href);
        return;
      }
      // Só a confirmação persistida do servidor permite apresentar a lista como pronta.
      if (request.status >= 200 && request.status < 300 && target.origin === window.location.origin
          && target.pathname === '/disparos' && target.searchParams.get('imported') === '1'
          && target.searchParams.get('list')) {
        status.textContent = 'Importação concluída. Abrindo a lista…';
        target.hash = 'lista-importada';
        window.location.assign(target.href);
        return;
      }
      const page = new DOMParser().parseFromString(request.responseText, 'text/html');
      const detail = page.querySelector('.alert.error span');
      fail(detail && detail.textContent.trim() || 'Não foi possível confirmar a importação. Confira as listas abaixo antes de tentar novamente.');
    });
    request.addEventListener('error', () => fail('Conexão interrompida. Atualize e confira as listas antes de tentar novamente.'));
    request.addEventListener('abort', () => fail('Importação interrompida. Confira as listas antes de tentar novamente.'));
    request.send(body);
  });
  window.addEventListener('pageshow', (event) => {
    if (event.persisted && busy) {
      restoreControls();
      show('error', name.textContent, 'Confira as listas importadas antes de reenviar este arquivo.');
    }
  });
})();
