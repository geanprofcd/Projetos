# H1-006P — comando humano atômico e formulário idempotente

16/10/2026. Aplicado exclusivamente na cópia Windows e no Supabase VENDRA-STAGING `ljufhqnadzltqbtdaulv`. Autorização explícita SQL15 recebida. Migration `vendra_whatsapp_human_command_v1` aplicada; ACL conferida: somente postgres/service_role, SECURITY INVOKER. SQL16 é reversão preparada, não executada. Nenhuma tabela/RLS nova, worker, lote ou transporte externo habilitado.

Uma única RPC faz handoff humano, mensagem, outbox e registro de idempotência na mesma transação. A chave fica em input oculto; o visual comercial permanece igual. Mesma chave/ator/ticket/texto recupera os mesmos IDs; texto diferente gera conflito. O adaptador não repete RPC após erro incerto, não expõe claim_token e conserva a chave no formulário de erro. Falha de notificação posterior não desfaz comando confirmado.

Somente texto WhatsApp sem anexos, sob a flag persistente existente e fora da demonstração, usa a RPC. Notas internas e anexos mantêm o caminho anterior. Notificação Make desabilitada na configuração atual; não comprova acionamento automático nem transmissão de anexos. SQL13 e etapa O já comprovaram envio humano real sob demanda até delivered.

## Evidências

Oito chamadas concorrentes reais: um comando novo/sete duplicatas, mesmos IDs, uma outbox pending, zero tentativas/WAMID. Handoff confirmado. Mesma chave/outro texto PT409; replay após encerramento recuperou comando. Janela e atendimento encerrados bloquearam comandos novos sem mensagem/outbox parcial; modo IA preservado na falha. Nove verificações de banco aprovadas; fixtures próprias removidas.

Regressão Windows isolada: 280 testes/2,955s/exit_code=0, relatório `staging_20261016_003130_742_d69cb681/resultado.json` em VENDRA-validacoes temporário. Erros simulados Storage/RPC são testes de falha. Unittest inicial diretamente no diretório com perfil privado foi interrompido; evidência válida é a cópia isolada sem configurações privadas. Testes HTTP comerciais constam no checkpoint abaixo; não há nova homologação visual pelo navegador.

Pasta/banco/design originais físicos intactos. Make originais mantêm callbacks STAGING autorizados e filtros de envio bloqueados; cenário humano O inativo. Railway sem deploy.

Próximo H01: acionamento automático seguro, mídia com vínculo/status por item, recuperação e padrão IA de novos atendimentos. Depois H02 criação/importação/lote comerciais; H03 backup/restauração/promoção seletiva; H04 hospedagem original/HTTPS estável. Não repetir contratos aprovados sem alteração relevante.

Checkpoint HTTP: oito verificações comerciais reais aprovadas: login, detalhe/chave oculta, primeiro POST303, repetição303, outro texto409, CSRF403, chave ausente422 e banco com uma mensagem/outbox sem tentativa/WAMID. Fixtures limpas/sessão revogada. Prévia8014 PID30756; nenhum envio externo. Fonte/pacote/Mestre em consolidação.
