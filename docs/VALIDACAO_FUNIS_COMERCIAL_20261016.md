# Funil original e regras comerciais - 16/10/2026

## Referencia correta

Configuracao lida na pasta ORIGINAL Windows, `.vendra-data/demo_state.json`, sem copiar o arquivo de estado, usuarios, clientes ou senhas. O original tinha um Funil Comercial com cinco etapas: Novo lead, Qualificacao, Proposta, Negociacao e Fechamento. O STAGING tinha apenas Funil Teste com tres etapas; o banco original hospedado tinha somente Novo Lead. SQL25 completou os cadastros ausentes, preservando o ID da etapa existente e o card real. Sete motivos de perda restaurados: Preco, Concorrente, Sem orcamento, Sem retorno, Prazo, Desistencia, Outro. Os nomes no banco mantem os acentos originais.

Backups privados de configuracao, sem clientes/senhas: backup_funis_staging_20261016.json (SHA256 4415ed1ba48ac304f2c7df30e3ddd1ec9dcd52b1c4e4b25e61b648ee7b4eb3c5) e backup_funis_original_20261016.json (d13505c3a3cf37978f6e182c17619e52372d149c27ab92e52ba5369598a950b6). Arquivos privados nao integram Git ou pacote publico.

## Erro de atualizacao de paginas

Logs Railway mostraram `httpx.RemoteProtocolError: Server disconnected` durante consulta Supabase no feed do Kanban. Hotfix de transporte: HTTP/1.1 explicito, keepalive curto, timeout limitado e uma unica recuperacao para GET/HEAD em RemoteProtocolError/ReadError. POST/PATCH/PUT/DELETE, RPCs de escrita e login nunca sao repetidos por esse mecanismo. Auth e backend mantem clientes separados; nao ha bypass de autenticacao, RLS ou permissao.

Primeiro deploy corretivo 0aa18f3d-3dd8-4a6d-832d-594280e35fc7 SUCCESS. Dezoito atualizacoes reais em seis paginas STAGING e dezoito online com Silas passaram; depois da primeira publicacao comercial outras dezoito online passaram. Isso verifica o caso observado; nao e garantia contra qualquer indisponibilidade futura do provedor.

## Regras executadas

- Primeira mensagem recebida do lead: recepcao SQL atomica identifica a primeira entrada, liga IA quando automacao global permite e nao existe pausa manual, incrementa versao e avanca Novo Lead para Qualificacao. Tudo ocorre antes do retorno do modulo64 e do filtro8 no Make. Mensagens seguintes preservam a decisao humana.
- Pausa Comercial: RPC existente autoriza Administrativo/Comercial/Gerencial ativos. Pause/read/reserva/versionamento continuam obrigatorios. Respostas tardias nao podem ignorar a versao atual; nenhum ator administrativo e usado em nome do Comercial.
- Calendly: somente mensagem externa de saida contendo URL HTTP(S) calendly.com ou www.calendly.com, com primeiro evento Meta delivered/read, avanca para Proposta. Aceite sent, texto apenas recebido, nota interna e dominio parecido nao autorizam esse avanco. Evento repetido ou read posterior a delivered nao repete movimentacao. Etapas posteriores, oportunidades ganhas/perdidas/arquivadas e funis inativos sao preservados.
- Ordem de Lista e Funil: conversas cuja ultima mensagem externa valida e recebida ficam primeiro; dentro de cada grupo, a atividade mais recente vem antes. Notas internas e saidas pending/failed/cancelled nao tomam a prioridade. A lista ordena no banco antes do limite/paginacao; o Kanban considera todos os cards carregados. Atualizacao automatica inclui atividade na assinatura do quadro.
- Make REV9 6534261: apenas filtro8 alterado para `64.data.automation.route_to_ai == true`; sequencia recepcao -> filtro -> IA preservada. Cenário continua ativo. Reservas e tres filtros de envio, conexoes, callbacks, janela de24h e destinatarios de producao preservados. Replays duplicados nao voltam a IA.

SQL26: duas RPCs novas, receive/status ajustadas e bind original preservado; SECURITY INVOKER, search_path vazio, EXECUTE backend service_role apenas. Sem tabelas novas, RLS nova, worker ou envio por efeito da migration. Migrations vendra_commercial_reply_calendly_activity_v1 e vendra_commercial_calendly_delivery_v2 aplicadas nos projetos corretos, sem dados STAGING copiados ao original. SQL27 reverte funcoes, nao executar automaticamente; reverter codigo de ordenacao antes de remover a RPC de atividade.

## Evidencias e limites

- 38 verificacoes funcionais do funil no STAGING e 38 online com Silas: cinco colunas, criar oportunidade/atendimento, itens e valor, movimentos, conflito409, CSRF403, ganho/perda/reabertura/arquivamento, historico, filtros e administracao403. Fixtures proprias limpas; nenhum WhatsApp enviado.
- 11 verificacoes HTTP/SDK reais STAGING de primeira resposta antes do Make, CONTINUE_TO_AI, qualificacao, desligamento Comercial, segunda entrada preservando humano, movimento manual e leitura de ordenacao. Fixtures limpas e configuracao global STAGING restaurada.
- SQL transacional integralmente revertido em STAGING e original: primeira resposta/controle IA, pausa Comercial, replay, reserva, vinculo sintetico Calendly, ausencia de avanco em sent, avanco em delivered, replay/read posterior preservando movimento manual, ordenacao e ACL. Sao eventos SINTETICOS de contrato; nao representam nova entrega real pela Meta.
- 56 testes Windows dos contratos afetados aprovados. Suite ampla foi interrompida apos ficar sem progresso e NAO conta como aprovada; nao foram modificadas assertions para contornar a interrupcao.
- Nova entrada real WhatsApp -> IA -> entrega apos esta mudanca ainda nao foi executada; reutilizamos o transporte real ja homologado e validamos especificamente os contratos alterados. Nao iniciar disparos para repetir testes fechados.

Portal: https://vendra-original-production.up.railway.app/atendimentos?view=funil

Deploy final: 797c35cf-6a1b-4237-ad3b-f4035bb36b99 SUCCESS. Sete arquivos de backend aplicados seletivamente no Windows original; ticket_service privado recebeu apenas duas funcoes. Backup HTTP e regras-comerciais preservado. Main/base/.env conferidos por hash. SQL26 final usa confirmacao delivered/read; a primeira revisao intermediaria baseada em sent foi substituida pela migration v2 e nao e o contrato final.

Nao e necessario instalar ou executar comandos para usar o portal. Atualizar a pagina carrega o conjunto publicado. Falha de screenshot anterior foi limite de uso da revisao automatica, nao recusa por risco; nenhuma captura nova alegada.

## Comandos documentados

```powershell
python -X utf8 -m unittest tests.test_database_http_client tests.test_conversation_order tests.test_whatsapp_commercial_backend tests.test_commercial_composer tests.test_commercial_dispatch_history tests.test_hosted_callbacks tests.test_production_phone_policy tests.test_dispatch_lists
Invoke-RestMethod https://vendra-original-production.up.railway.app/health
```

Atualizacao de outra copia original requer o pacote seletivo e backup. `tools/aplicar_ordem_comercial_original.py --target CAMINHO/app/services/ticket_service.py` faz previa; `--apply` aplica apenas duas funcoes e guarda backup. Nao copiar o ticket_service inteiro do STAGING sobre o original. SQL/Make sao operacoes separadas e ja foram executadas nesta entrega, nao reaplicar por copiar arquivos.
