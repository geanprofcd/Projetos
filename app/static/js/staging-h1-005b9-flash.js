/* H1-005B9 HOTFIX: confirmacao unica apos PRG. Sem cookies nem dados na URL. */
(() => {
  "use strict";
  const notice = document.querySelector('[data-vendra-b9-flash]');
  if (!notice || !window.history || !window.history.replaceState) return;
  try {
    const url = new URL(window.location.href);
    const result = url.searchParams.get('resultado');
    const warning = url.searchParams.get('aviso');
    const successValid = result === 'preparado' || result === 'alterado';
    const warningValid = ['conflito', 'estado', 'permissao'].includes(warning);
    if (result !== 'preparado' && result !== 'alterado' && !warningValid) return;
    if (successValid) url.searchParams.delete('resultado');
    if (warningValid) url.searchParams.delete('aviso');
    const cleaned = url.pathname + url.search + url.hash;
    window.history.replaceState(window.history.state, '', cleaned);
  } catch (_) {
    // A confirmacao e o bloqueio de envio continuam seguros se a limpeza da URL falhar.
  }
})();
