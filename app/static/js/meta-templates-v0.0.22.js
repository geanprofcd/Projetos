(() => {
  const overlay = document.querySelector('#templateOverlay');
  if (!overlay) return;
  const root = document.querySelector('#ticketLiveRoot');
  const list = document.querySelector('#templateOptions');
  const info = document.querySelector('#templateMessage');
  const previewBox = document.querySelector('#templatePreviewBox');
  const previewText = document.querySelector('#templatePreview');
  const varsBox = document.querySelector('#templateVariables');
  const chosenName = document.querySelector('#templateSelectedName');
  const chosenLang = document.querySelector('#templateSelectedLanguage');
  const valuesJson = document.querySelector('#templateValuesJson');
  const sendButton = document.querySelector('#templateSendButton');
  const sendForm = document.querySelector('#templateSendForm');
  const createForm = document.querySelector('#templateCreateForm');
  const newBody = document.querySelector('#templateNewBody');
  const exampleBox = document.querySelector('#templateExamples');
  const examplesJson = document.querySelector('#templateExampleJson');
  let selected = null;
  let lastFocus = null;
  let loaded = false;
  const ticketId = root.dataset.ticketId;

  function selectTab(id) {
    overlay.querySelectorAll('[data-template-tab]').forEach(btn => {
      const active = btn.dataset.templateTab === id;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-selected', String(active));
    });
    overlay.querySelectorAll('[data-template-panel]').forEach(el => {
      el.hidden = el.dataset.templatePanel !== id;
    });
  }

  function show() {
    lastFocus = document.activeElement;
    overlay.hidden = false;
    document.body.classList.add('template-modal-open');
    overlay.querySelector('.template-close').focus();
    if (!loaded) load();
  }
  function hide() {
    overlay.hidden = true;
    document.body.classList.remove('template-modal-open');
    lastFocus?.focus();
  }
  document.querySelectorAll('[data-open-template-modal]').forEach(el => el.addEventListener('click', show));
  overlay.querySelectorAll('[data-close-template-modal]').forEach(el => el.addEventListener('click', hide));
  overlay.querySelectorAll('[data-template-tab]').forEach(el => el.addEventListener('click', () => selectTab(el.dataset.templateTab)));
  overlay.addEventListener('click', e => {if (e.target === overlay) hide();});
  document.addEventListener('keydown', e => {
    if (overlay.hidden) return;
    if (e.key === 'Escape') hide();
    if (e.key !== 'Tab') return;
    const focusable = [...overlay.querySelectorAll('button:not(:disabled):not([hidden]),input:not(:disabled),textarea:not(:disabled),select:not(:disabled)')]
      .filter(x => x.getClientRects().length);
    if (!focusable.length) return;
    const first = focusable[0], last = focusable.at(-1);
    if (e.shiftKey && document.activeElement === first) {e.preventDefault();last.focus();}
    if (!e.shiftKey && document.activeElement === last) {e.preventDefault();first.focus();}
  });

  async function load() {
    info.textContent = 'Consultando a conta WhatsApp na Meta...';
    list.replaceChildren();
    chosenName.value = '';
    selected = null;
    sendButton.disabled = true;
    previewBox.hidden = true;
    try {
      const response = await fetch(`/atendimentos/${encodeURIComponent(ticketId)}/modelos.json`, {credentials:'same-origin',headers:{Accept:'application/json'}});
      const data = await response.json();
      if (!response.ok || data.message) {info.textContent = data.message || 'Não foi possível consultar os modelos.';loaded=false;return;}
      loaded=true;
      const items = data.templates || [];
      if (!items.length) {info.textContent = 'Nenhum modelo de texto localizado nesta conta. Você pode criar um novo na aba ao lado.';return;}
      const approved = items.filter(x => x.status === 'APPROVED');
      info.textContent = `${approved.length} aprovado(s) · ${items.length - approved.length} em análise, rejeitado(s) ou indisponíveis`;
      items.forEach(item => {
        const btn = document.createElement('button'); btn.type='button';btn.className='template-option';
        btn.disabled = item.status !== 'APPROVED';
        const heading=document.createElement('strong');heading.textContent=item.name.replaceAll('_',' ');
        const badge=document.createElement('span');badge.className=`template-status ${item.status==='APPROVED'?'is-approved':'is-pending'}`;
        badge.textContent = ({APPROVED:'Aprovado',PENDING:'Em análise',REJECTED:'Rejeitado',PAUSED:'Pausado',DISABLED:'Desativado'})[item.status] || item.status;
        const summary=document.createElement('small');summary.textContent=item.body;
        btn.append(heading,badge,summary);
        btn.addEventListener('click',()=>choose(item,btn));
        list.append(btn);
      });
    } catch (_) {info.textContent='Não foi possível consultar a Meta. Verifique sua conexão.';loaded=false;}
  }
  document.querySelector('#templateRefresh').addEventListener('click', () => {loaded=false;load();});
  function choose(item,btn) {
    selected=item;
    chosenName.value=item.name;
    chosenLang.value=item.language;
    list.querySelectorAll('.template-option').forEach(x=>x.classList.remove('selected'));
    btn.classList.add('selected');
    previewBox.hidden=false;
    varsBox.replaceChildren();
    for (let index=1;index<=item.variables;index++) {
      const label=document.createElement('label');label.textContent=`Variável {{${index}}}`;
      const input=document.createElement('input');input.required=true;input.maxLength=200;input.placeholder=`Texto para variável ${index}`;
      input.className='template-value';
      input.addEventListener('input', refreshPreview);
      label.append(input);varsBox.append(label);
    }
    refreshPreview();
  }
  function refreshPreview() {
    if (!selected) return;
    const values=[...varsBox.querySelectorAll('input')].map(x=>x.value.trim());
    valuesJson.value=JSON.stringify(values);
    let text=selected.body;
    values.forEach((v,i)=>{text=text.replaceAll(`{{${i+1}}}`,v||`[${i+1}]`);});
    previewText.textContent=text;
    sendButton.disabled=values.some(x=>!x);
  }
  sendForm.addEventListener('submit',e=>{
    if (!selected || selected.status!=='APPROVED' || sendButton.disabled) {e.preventDefault();return;}
    if (!window.confirm(`Confirmar envio de "${selected.name}" para esta conversa?`)) {e.preventDefault();return;}
    sendButton.disabled=true;sendButton.textContent='Enviando...';
  });
  function indexes(body) {
    const ids=new Set([...body.matchAll(/\{\{(\d+)\}\}/g)].map(x=>Number(x[1])));
    if (!ids.size)return 0;
    const max=Math.max(...ids);
    return max<=5 && ids.size===max ? max : -1;
  }
  function refreshExampleInputs() {
    const count=indexes(newBody.value);
    exampleBox.replaceChildren();
    if (count<0) {exampleBox.textContent='Use variáveis numeradas em sequência, de {{1}} até {{5}}.';return;}
    for (let i=1;i<=count;i++) {
      const label=document.createElement('label');label.textContent=`Exemplo de {{${i}}} para a Meta`;
      const input=document.createElement('input');input.className='template-example';input.maxLength=100;input.required=true;
      input.placeholder=i===1?'Maria':'Exemplo';label.append(input);exampleBox.append(label);
    }
  }
  newBody.addEventListener('input', refreshExampleInputs);
  createForm.addEventListener('submit',e=>{
    const count=indexes(newBody.value);
    if (count<0){e.preventDefault();newBody.focus();return;}
    const samples=[...exampleBox.querySelectorAll('input')].map(x=>x.value.trim());
    if (samples.some(x=>!x)) {e.preventDefault();return;}
    examplesJson.value=JSON.stringify(samples);
    const submit=document.querySelector('#templateCreateButton');submit.disabled=true;submit.textContent='Enviando para análise...';
  });
  refreshExampleInputs();
  if (!overlay.hidden) show();
})();
