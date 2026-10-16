# H1-006O - Reserva exclusiva e texto humano entregue

Rodada de 15-16/10/2026, somente código/banco STAGING, com cenário Make de teste sob demanda. Pasta, banco e design originais preservados. Esta rodada fecha a reserva exclusiva e a transmissão de texto humano com confirmação real; não declara toda a automação comercial concluída.

## Mudança aplicada

SQL13 aplicado após autorização textual específica, migration `vendra_whatsapp_human_reservation_v1`. Cria somente `vendra_whatsapp_human_prepare_v1(uuid)`, SECURITY INVOKER/search_path vazio/EXECUTE apenas service_role. O ajuste `vendra_whatsapp_human_text_limit_v1` limita texto a4096caracteres, dentro do mesmo contrato autorizado. SQL14 de reversão preparado, não executado. Nenhuma tabela ou RLS alterada.

A reserva bloqueia ticket/outbox na mesma ordem do handoff, concede somente uma autorização e não devolve token/corpo em repetição. Exige atendimento WhatsApp aberto/humano, janela válida, autor ativo Adm/Com/Ger, cliente/telefone coerentes, mensagem humana pendente e sem anexo. Não recupera automaticamente uma reserva claimed: resultado incerto não é autorização de reenvio. Anexos ficam bloqueados até seu contrato próprio, evitando transmissão parcial com vários WAMIDs.

Nova rota `/webhooks/make/whatsapp/outbox/{id}/prepare-human` sob flag `VENDRA_BRIDGE_HUMAN_ENABLED=false` por padrão; segredo, conta/remetente e destinatário já autorizado conferidos antes/depois da RPC. Resposta malformada do banco falha fechada. Ponte não envia mensagens diretamente nem publica polling/worker. Flag privada foi ligada só durante a rodada autorizada e restaurada ao final.

## Falha encontrada e corrigida

Duas tentativas com oito callbacks simultâneos retornaram503 por RemoteProtocolError no acesso ao Supabase, antes da reserva. Fixtures limpas e tentativas não contadas como aprovação. Diagnóstico com leituras simples não reproduziu o erro; não foi usado como prova de ausência da falha. A ponte passou a usar cliente HTTP/1.1 explícito, sem sessão/refresh Auth de backend e com encerramento do transporte no shutdown. A mesma carga real então passou. Isso demonstra a correção nesse fluxo/ambiente, sem afirmar uma causa universal para todo erro de rede Windows.

Logs novos registram somente classe técnica da exceção, sem payload, chave ou token. Escritas não são repetidas automaticamente; implementação instalada do SDK só faz retry automático de GET/HEAD em503/520. HTTP1 foi alterado na ponte, não no banco/folder original nem no cliente Auth do portal.

## Evidências

- **18 verificações reais HTTP/RPC/banco** com fixtures próprias: segredo ausente/conta divergente; oito pedidos simultâneos com um vencedor/sete supressões; suprimidos sem corpo/token; tentativa única claimed; equivalência BR12/13; token de outro worker rejeitado; vínculo/WAMID sintéticos e status associado; outro WAMID rejeitado; replay bloqueado; janela fechada/modoIA/ticketencerrado/anexos bloqueados; texto4097/telefone divergente/autor inativo rejeitados. Eventos/WAMID dessas fixtures eram sintéticos e foram removidos. Nenhuma mensagem ao provedor nesses18casos.
- **Envio humano real**, depois de criar a mensagem pelo composer comercial8014, na conversa exclusiva com entrada real anterior e número87988216094 autorizado. Cenário de teste6654745: `fd2aeee1a2844892b0cb11d7d741963f`, 16/10/2026 00:03:39 Brasília, 5,360s. Executou1/2/3/4/5/6; um módulo WhatsApp4, uma reserva e um vínculo de WAMID. Sem erro.
- **Delivered real automático** recebido pelo REV9 original e persistido no STAGING: `c4bf4dc8c62d4b18a291a3a48fc56420`, 00:03:47 Brasília, módulos71/83, HTTP202/acceptedtrue/updatedtrue/pending_matchfalse/statusdelivered. O vínculo da outbox aponta para a mensagem humana e seu delivery_status acompanha o evento. Não alegar read nesta rodada.
- **Replay do mesmo pedido**: `638055adcf594956972751220c37cf51`, 00:04:31 Brasília, somente1/2/3; módulo WhatsApp4 não executado. Banco manteve uma tentativa, uma mensagem para a solicitação e o mesmo WAMID. Isso homologa replay da mesma outbox, não duplo clique que crie duas outboxes.
- **273 testes Windows em1,569s**, snapshot limpo/UTF8, relatório privado `VENDRA-validacoes/staging_20261016_000651_157_a83700c9/resultado.json`. Dez novos casos da rota humana/fechamento de recursos. Tracebacks de falhas simuladas esperadas não indicam falha da suíte.

Primeiro probe do cenário novo não enviou/ reservou: faltavam campos avançados obrigatórios do HTTPv4. Corrigidos stopOnHttpError/timeout/redirects/cookies/compressão, probe `eb71e114229b4ffab5343f4a58ec081d` confirmou health200 e apenas1/2. A reserva de saída real só foi criada/executada após essa conferência.

## Túnel e Make

Túnel temporário8013 expirou (Unauthorized: Tunnel not found). Renovado dentro da autorização existente, sem tocar8012. Backup privado dos dois cenários originais salvo antes de trocar somente host nos oito callbacks REV9 e dois do Disparo Inicial. Mappers/segredos/conexões/filtros preservados; provider77/75/76 e template2 continuam bloqueados por condição constante. Cópias antigas inativas não foram reconfiguradas sem necessidade.

Novo cenário6654745 criado separado, sob demanda, sem agenda/polling/webhook amplo. Israel11704121/remetente1304357726102369 resolvidos pela conta. Gate de envio limitado à única outbox/telefone de teste. Ao terminar, módulo4 com condição constantefalse e cenário inativo. Ponte com flag humana desligada; atendimento exclusivo encerrado em humano e responsável anterior restaurado. Evidência real entregue preservada; contas CODEX não excluídas. Nenhum worker contínuo/lote habilitado.

## Links e comandos

[Envio real](https://us2.make.com/292724/scenarios/6654745/logs/fd2aeee1a2844892b0cb11d7d741963f) | [Delivered automático](https://us2.make.com/292724/scenarios/6534261/logs/c4bf4dc8c62d4b18a291a3a48fc56420) | [Replay sem segundo envio](https://us2.make.com/292724/scenarios/6654745/logs/638055adcf594956972751220c37cf51)

Código já aplicado na cópia, sem reinstalação manual necessária. Conferência não mutante e regressão:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8013/health'
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

Health deve informar STAGING/external_sends_enabledfalse/human_enabledfalse em repouso. Não iniciar outra ponte na8013. Se necessário reiniciar após verificar porta livre: `.\.venv\Scripts\python.exe -X utf8 -m tools.whatsapp_callbacks_start --config 'CAMINHO_DO_PERFIL_EXCLUSIVO_STAGING.env' --port 8013`. Não usar.env original ou publicar perfil privado. Instalador de arquivos não aplicaSQL13/14 nem ativaMake.

## Próxima pendência concreta

H01 do [mapa de homologação](MAPA_HOMOLOGACAO_ORIGINAL.md): idempotência do formulário e acionamento automático da saída humana. A reserva exclusiva está encerrada; não retestar recepção/IA/template por este motivo. Mídia e padrão IA de novos atendimentos continuam na mesma frente. H02 Disparos comerciais; H03 promoção/backup; H04 hospedagem final.
