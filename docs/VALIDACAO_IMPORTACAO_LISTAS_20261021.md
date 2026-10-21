# Importação: arquivo visível, progresso e carga de 20 mil — 21/10/2026

## Resultado e limites

A área comercial demarcada agora mostra o nome do arquivo selecionado. Ao clicar em Importar e revisar, um círculo animado permanece durante o upload e o processamento. Após confirmação persistida do servidor, abre a lista correspondente e o mesmo local apresenta o arquivo e a quantidade de contatos aptos. O nome permanece após atualizar ou selecionar uma lista existente.

Mudança restrita a três arquivos: app/templates/dispatches/list.html, app/static/js/dispatch-upload-v0.0.27.js e app/static/css/dispatch-upload-v0.0.27.css. Sem alteração de SQL, backend, cenários Make, permissões, transportes ou formato de importação. Não se trata de guardar o arquivo binário para download: o nome corresponde à lista persistida já existente.

Estados: vazio, selecionado, carregando, pronto e erro. Arquivo/CSRF capturados antes de desabilitar controles; duplo clique bloqueado. Progresso real do upload quando disponível; após transferência, estado de validação. Somente redirect de sucesso com identificador de lista permite navegação. Erros preservam o nome, reabilitam controles e orientam conferir listas antes de repetir. Nenhum retry automático. Nomes tratados como texto/escape Jinja. Movimento reduzido e status acessível suportados.

## Validação da interface e fluxo

- 18 verificações Edge headless com template comercial real e servidor HTTP local controlado: nome, spinner, CSRF multipart, um POST, redirect, persistência após refresh, celular, nome com caracteres HTML sem execução, erro422, controles restaurados, ausência de retry, movimento reduzido e ausência de erros JS. Este servidor simula somente a resposta HTTP; não equivale a integração de banco.
- 9 verificações HTTP/SDK reais no STAGING: login Comercial, tela, rejeição CSRF403, upload303 com persistência real, nome no local solicitado, refresh, arquivo vazio422 e dois assets200. Flag de disponibilidade sobrescrita apenas no processo de teste; flags globais/transportes/worker não habilitados. Sessão própria encerrada e fixture da importação/auditoria removidas.
- 8 testes existentes de listas Windows passaram em0,044s. Não contados como funcionalidades novas.

## Carga e concorrência reais no STAGING

10 verificações passaram. CSV sintético com20.001 linhas limitado a20.000, todos normalizados/aptos; aviso do limite;40 páginas da Data API recuperadas sem perdas e em ordem. Oito chamadas concorrentes à RPC existente de início da mesma lista retornaram a mesma lista com bulk_total20.000. Exatamente20.000 itens queued, nenhuma duplicação ou dispatch_id. Worker local bloqueado antes de consultar/claim; flag global dispatch_lists permaneceu desligada. Os20.000 registros e sua lista exclusivos CODEX foram removidos e ausência conferida. Nenhum dado/canal original acessado por esse ensaio.

Observações locais, sem promessa de SLA: importação24,617s, leitura completa26,897s, oito inícios simultâneos1,567s. Não equivale a20.000 envios, renderização20k no navegador, teste de múltiplos operadores autenticados, claim concorrente de workers ou entrega pelo provedor. Essas partes não foram simuladas como homologação completa.

## Aplicação original e publicação pendente

Somente os três arquivos da interface aplicados à pasta original Windows e release privada. Backup: output/backups/upload-lista-original-20261021 no original, com manifesto/hashes. .env, main.py, base.html, router e serviços de listas preservados por hash. Commit privado985fb6f2332b3a50da4674df206953118af25fe8.

Railway up recusado com Unauthorized; consulta de deployments falhou. Login pelo GitHub já vinculado restabeleceu acesso ao painel. O próprio painel informa incidente de API e builds pausados; página oficial confirma em21/10: https://status.railway.com/incident/QH8L8B3E (última atualização observada13:40UTC/10:40Brasília). Não concluir que o token expirou somente pelo erro da CLI; nenhuma credencial substituída.

Não houve novo deployment confirmado. O site hospedado continua na release anterior; a alteração visual NÃO está publicada até restabelecer a plataforma e verificar o deploy. Login e callbacks/health hospedados responderam200 nesta rodada. Nenhum cenário Make pausado/modificado, nenhuma mensagem enviada, nenhuma variável de produção alterada. VENDAXIS permanece separado e somente local.

## Comandos de referência

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_dispatch_lists
```

Na release privada vinculada ao projeto existente, com autenticação restrita válida, após o Railway voltar:

```powershell
railway up --service vendra-original --environment production --detach --message "Feedback visual de importacao de listas homologado no STAGING"
railway deployment list --service vendra-original --environment production --json
```

Não executar na pasta STAGING nem criar outro projeto. Confirmar SUCCESS e os assets/template hospedados antes de declarar entregue online. Se persistir Unauthorized após normalização da plataforma, conferir o acesso restrito sem expor tokens no chat. Reversão: restaurar apenas os arquivos existentes do backup e remover os dois assets adicionados da release, preservando configurações; publicar a release revisada. Não tocar nas listas reais ou pausar o Make.
