# H1-006F — Disparo Inicial persistente e template real

15/10/2026, Brasília. Continua H1-006E. Usuário reforçou autonomia para agilizar e copiar componentes do VENDRA original quando necessário, preservando o original e a separação de configurações/dados. Documento Mestre é atualizado por entregas consolidadas, sem encerrar o desenvolvimento após cada atualização.

## Aplicado

- Código em app/whatsapp_callbacks.py: flag VENDRA_BRIDGE_DISPATCH_ENABLED explícita, false por padrão; reserva e confirmação de disparo autenticadas por segredo, conta/remetente, destinatário e entidades reais. Não importa portal/demo_store, abre fila ou envia diretamente à Meta.
- Com autorização específica, aplicadas somente no projeto STAGING ljufhqnadzltqbtdaulv as migrations vendra_dispatch_control_bind_v1 e vendra_dispatch_message_wamid_fix_v1. Três funções SECURITY INVOKER, search_path vazio, EXECUTE apenas service_role. Tabelas/RLS não alteradas; flags não habilitadas pela migration.
- SQL 06 é a primeira revisão aplicada; SQL 08 corrige a confirmação para gravar também messages.external_message_id, além de dispatches e whatsapp_outbox. Aplicar ambas na ordem 06 → 08 depois de H1-006B. SQL 07 é rollback separado das três funções, sem apagar dados; exige desconectar consumidores primeiro. Não executar automaticamente por copiar o pacote.
- Cópia Make 6643860, sob demanda, sem webhook Meta; normalização e template copiados do cenário original, remetente Israel e template continuar_atendimento_vendra::pt_BR resolvidos pela conta. Contrato novo reserva antes de enviar e confirma por outbox/token/WAMID. Template usa o nome persistido retornado pelo banco.
- Ponte diagnóstica 8013 atualizada; perfil explícito com dispatch_enabled=true permite registrar rotas, mas configuração global dispatch_bridge permanece ausente ao encerrar. 8010/8011/original/ponte8012 sem alteração operacional nesta rodada.

## Validação

| Verificação | Resultado |
|---|---|
| Seis casos Make de normalização, sem envio | Pontuação, número sem nono dígito, prefixo 0055, zero inicial normalizados; curto e estrangeiro rejeitados |
| 43 testes focados Python | Aprovados; 12 novos de autenticação, escopo, flag, nome/base64, token e wrapper de status |
| Regressão Windows em cópia limpa | 200 testes aprovados, 1,703 s; Python -X utf8, sem copiar venv/perfis/estado |
| Contratos reais HTTP/Supabase | 22 verificações aprovadas após a correção SQL, com limpeza confirmada e nenhum envio |
| Concorrência | Oito conexões independentes: uma reserva autorizada e sete duplicatas sem token; uma única outbox |
| Cenário com flag global desligada | 4cb0104e6b624788b5e3000f092c3626: HTTP 202 suprimido; disparo pending, zero reserva/envio |
| Template real autorizado | 3513da070690451583c8f83f25697b49, 15/10 09:39:23 Brasília; normalização → reserva100 → template2 → confirmação101; uma mensagem enviada |
| Evento Meta real delivered | 87f707d69652442290711c4aea49ab8b recebido no original; WAMID conferido e payload copiado para auxiliar a20b70bdab784504be63af41e5cde7aa, HTTP202 |
| Consistência final | dispatches, messages e whatsapp_outbox em delivered com o mesmo WAMID; confirmação repetida após correção não enviou mensagem e reconciliou zero |
| Limpeza e desligamento | Consulta independente: flags dispatch_bridge/whatsapp_bridge=0, clientes sintéticos CODEX-DISPATCH=0, entrada real anterior preservada=1 |

Os 22 checks reais incluem flag desligada, payload divergente, solicitante sem permissão, atendimento encerrado, concorrência, texto renderizado, replay, status sintéticos anteriores ao vínculo, token errado, confirmação com flag desligada, consistência dos três registros, repetição e ausência de regressão. Status sintéticos não representam novas entregas Meta; a linha delivered real acima é evidência separada.

## Falhas corrigidas e rastreabilidade

1. Primeiro remanejamento Make deixou HTTP100 depois do envio, apesar da confirmação de operações aplicadas. Execução 8c2d30b2e2074a02a2420c197b23cf18 recusou inicialização, sem operar. Estrutura relida e corrigida para 1 → 4 → 100 → router5, envio2 → confirmação101 e retorno99. Reteste passou. Não atribuir sucesso à primeira tentativa.
2. Confirmação original gravava WAMID no disparo/outbox, mas não no campo da mensagem. Conferência real detectou; SQL08 corrigiu a RPC, teste remoto ganhou a verificação explícita e passou. Callback do mesmo WAMID repetido sem enviar novamente. Mesma correção protege contra conflito com WAMID já existente na mensagem.
3. Uma tentativa de repetir a fixture sintética foi bloqueada pelo pré-check porque os endpoints públicos de disparo estavam ligados. Perfil público foi temporariamente fechado; validação ocorreu somente em TestClient não publicado e consumidores protegidos. Perfil diagnóstico restaurado após limpar a flag/fixture.

Backup do callback anterior fora do repositório: SHA-256 cdeb3834826375887e867e93431860fe6b8c1aa3d83c978c30f8cb3e23bdb5aa. SQL/Make/perfis privados são operações separadas. Não publicar segredos, payloads pessoais, claim_token ou backups de cenário.

## Estado ao encerrar os testes deste marco

Cópias Make 6643860 e 6640168 inativas; bloqueio constante do template restaurado; flags globais ausentes; atendimento exclusivo CODEX-TEMPLATE encerrado, evidência real preservada. Contas CODEX mantidas até homologação total. Original REV9/Disparo Inicial e callback Meta original preservados. Não promover snapshot nem dados/credenciais.

## Próxima etapa em andamento: recepção contínua

Os status reais desta rodada foram copiados do cenário receptor, cujo destino temporário anterior está indisponível. Isso comprova processamento/persistência do evento, não recepção automática contínua na cópia. Leitura real do template ainda não comprovada. Entrada do teste veio de interface sob demanda e disparo persistido preparado exclusivamente para homologação; não comprova disparo pelo portal/CRM real.

A conta Meta possui aplicativo existente com callback Make já configurado; não substituir esse callback. Foi iniciada a criação oficial de aplicativo de teste VENDRA-STAGING-CODEX, mas a Meta pediu reautenticação por senha. A criação ainda depende da confirmação dessa etapa; não registrar app criado sem evidência. Enquanto aguarda, continuar código/testes/entrega independentes. Não pedir senha no chat nem alterar credenciais.

Restam: concluir isolamento da assinatura/recepção Meta, integrar os comandos do portal/CRM ao transporte real com os controles de permissão existentes, validar recuperação operacional e HTTPS estável, homologar o conjunto final e promover seletivamente com backup/rollback. Não repetir envio real já entregue sem motivo.

## Links e comandos

- [Cópia Disparo Inicial](https://us2.make.com/292724/scenarios/6643860/edit)
- [Template e vínculo reais](https://us2.make.com/292724/scenarios/6643860/logs/3513da070690451583c8f83f25697b49)
- [Delivered real persistido](https://us2.make.com/292724/scenarios/6640168/logs/a20b70bdab784504be63af41e5cde7aa)
- [Fonte STAGING](https://github.com/geanprofcd/Projetos/tree/desenvolvimento/vendra-staging)

Runtime preparado, testes focados (executados nesta rodada; comando para consulta):

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_whatsapp_callbacks tests.test_whatsapp_control_bridge tests.test_whatsapp_dispatch_bridge -q
```

Startup diagnóstico usa perfil privado explícito, sem herdar .env do original:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.whatsapp_callbacks_start --config 'PERFIL_PRIVADO_STAGING' --port 8013
```

Esse comando apenas inicia o processo; não garante SQL aplicado, configuração global ativa, Make ligado ou envio. Evitar iniciar segunda instância se a porta já estiver em uso. Nenhuma execução manual é necessária pelo usuário para os arquivos já aplicados no Windows desta sessão.
