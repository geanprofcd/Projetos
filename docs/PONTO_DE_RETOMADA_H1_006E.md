# VENDRA — ponto de retomada H1-006E

Registro em 15/10/2026; testes iniciados em 14/10, horário de Brasília.

## Onde estamos

Integração WhatsApp/Meta → Make → VENDRA-STAGING → IA em homologação parcial. Recepção e persistência reais já foram comprovadas; agente, arquivos e consulta Knowledge foram exercitados na cópia Make. Preparação de resposta, controle, vínculo e reconciliação passaram em testes separados. O ciclo completo com resposta enviada pela IA e confirmação real do provedor ainda não foi homologado. Nenhuma promoção ao VENDRA original.

O código público permanece 0.0.25 com incrementos de STAGING. Fonte versionado até H1-006D: commit `9846a55a7b318b3e5f051125345d8450aa72cd2b`. Este checkpoint documental não constitui nova entrega de aplicação. A ferramenta local `tools/whatsapp_callbacks_contract_check.py` foi executada; sua revisão, versionamento e pacote Windows ainda devem ser concluídos antes de tratá-la como entrega publicada.

## Evidências concluídas

- Canal Meta Israel: envio autorizado entregue/lido e resposta recebida, conforme checkpoints anteriores. Recepção real persistida no STAGING mantendo WAMID e timestamp originais.
- Banco STAGING: RPCs de recepção/status e controle/vínculo aplicadas; funções restritas a service_role. Nenhum SQL novo nesta rodada.
- H1-006D: 21 verificações reais de concorrência com oito conexões independentes; duplicatas, CAS, handoff e vínculo/status conferidos.
- H1-006E: agente respondeu usando arquivos; outro teste consultou Knowledge com sucesso. Execuções sem envio e sem preparação de outbox pelas rotas diagnósticas.
- 18 verificações HTTP com Supabase real: preparação usando o texto retornado pelo agente, idempotência, conflitos, bloqueios, handoff, token e reconciliação. Fixtures removidas e flag global restaurada.
- Seis casos Make → HTTPS → ponte 8013 → STAGING: resposta bloqueada com HTTP 202; delivered/read sintéticos pendentes; token incorreto rejeitado com HTTP 403; vínculo reconciliou dois status até read; repetição reconciliou zero. Conferência posterior confirmou outbox/mensagem em read e nenhum status pendente. Fixture removida por IDs e escopo conferidos; cliente e entrada reais preservados.
- 188 testes Windows de regressão aprovados em cópia limpa (1,221 s); 31 testes focados já aprovados. Isso não substitui homologação funcional do ciclo completo.

Status delivered/read desta rodada são simulados: não representam uma nova entrega real da Meta. Nenhuma nova mensagem externa foi enviada nesta etapa.

## Ambiente e preservação

- Portal STAGING 8011 e ponte 8012 preservados; ponte 8012 com IA/envio desligados.
- Ponte diagnóstica separada em 127.0.0.1:8013, com segredo próprio e túnel Cloudflare temporário explicitamente autorizado. Rotas de IA registradas; configuração global do banco desligada ao encerrar. Ponte não envia diretamente ao provedor.
- Cópia REV9 `6639761`: sob demanda, sem webhook/assinatura Meta; três módulos de envio mantêm bloqueio constante. Testes diagnósticos não acionam as rotas normais de preparação de resposta. Terminou desativada.
- Auxiliar `6640168`: somente contratos HTTP, sem módulo Meta/envio; terminou desativado.
- Original REV9 `6534261` sem nova edição nesta rodada; preservar também o Disparo Inicial, túneis, configurações e dados do original. Alterações históricas autorizadas não foram revertidas automaticamente.
- Contas CODEX continuam para testes; excluir somente após homologação total, conforme instrução do usuário.
- Não existe servidor de nuvem permanente confirmado. Git registra fontes/evidências; Documento Mestre registra requisitos, decisões e evolução. Pacote publicado não equivale a aplicação no original.

## Etapas que faltam, em ordem

1. **Fechar a entrega H1-006E:** revisar/versionar a ferramenta de contratos, atualizar manifesto de hashes, sincronizar o checkout Git separado e publicar pacote Windows com instruções/backup. Este checkpoint e o Mestre documentam o avanço já executado.
2. **Unir as partes no fluxo normal da cópia REV9:** nova entrada controlada → controle de atendimento → agente/Knowledge → preparação de resposta → outbox. Validar texto, destinatário, deduplicação e janela. O modo diagnóstico atual não comprova essa união.
3. **Homologar passagem para humano e falhas no fluxo completo:** resposta tardia, duplicação/replay, concorrência, indisponibilidade, reserva em voo e recuperação sem duplicar envio. Revisar pendências claimed quando houver conflito após reserva.
4. **Executar saída real controlada:** liberar apenas o caminho necessário na cópia para o destinatário já autorizado; provar envio pela conta Israel, vínculo do WAMID real, delivered/read e persistência. Não liberar disparos gerais por efeito desses testes.
5. **Criar e testar cópia isolada do Disparo Inicial:** conexão Israel, template aprovado e parâmetros, normalização BR, persistência, vínculo/status e prevenção de duplicidade. Preservar o cenário original.
6. **Consolidar conexão/recepção Meta e templates dos dois cenários:** comprovar comportamento de ponta a ponta no desenho final de STAGING, incluindo webhook compatível com o isolamento. A cópia atual não possui assinatura Meta própria.
7. **Preparar hospedagem e operação estável:** substituir dependência de túneis temporários por domínio/HTTPS estáveis; configuração e segredos separados, startup, monitoramento, backup e recuperação. Fazer levantamento dos componentes ainda fora da base inicial Git (launcher Go e migration local 003) antes de incluí-los.
8. **Homologar o conjunto final e promover seletivamente:** registrar evidências relevantes e ausência de regressões; backup, manifesto e rollback; aplicar somente arquivos/configurações homologados no VENDRA original. Não copiar snapshot, credenciais, dados ou migrations não validadas.
9. **Encerrar testes:** remover contas CODEX autorizadas e fixtures remanescentes, desativar auxiliares/túneis temporários que não sejam mais necessários e atualizar Mestre e comandos finais.

## Próxima ação concreta

Concluir a entrega rastreável H1-006E e depois exercitar a rota normal de resposta na cópia REV9, mantendo os envios bloqueados até essa validação. Não é necessário o usuário executar comandos agora.

## Links e comandos para consulta

- [Fonte STAGING](https://github.com/geanprofcd/Projetos/tree/desenvolvimento/vendra-staging)
- [Commit de aplicação H1-006D](https://github.com/geanprofcd/Projetos/commit/9846a55a7b318b3e5f051125345d8450aa72cd2b)
- [Cópia REV9](https://us2.make.com/292724/scenarios/6639761/edit)
- [Agente com Knowledge](https://us2.make.com/292724/scenarios/6639761/logs/8eb089e933d54fd690f2815ef227555f)
- [Auxiliar HTTP](https://us2.make.com/292724/scenarios/6640168/edit)
- [Vínculo e reconciliação](https://us2.make.com/292724/scenarios/6640168/logs/378fa2acd1844836b30590053f5d4d6d)

Sincronizar apenas o checkout Git separado, preservando alterações locais:

```powershell
$repo = 'C:\Users\israe\Downloads\Automações\VENDRA-GIT-STAGING'
git -C $repo fetch origin
if (git -C $repo status --porcelain) { throw 'Revisar alterações locais antes de sincronizar' }
git -C $repo pull --ff-only
git -C $repo log -1 --oneline
```

Testes direcionados, no runtime STAGING preparado:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_whatsapp_callbacks tests.test_whatsapp_control_bridge -v
```

Comandos documentados para consulta; não representam novos testes executados neste checkpoint. Não compartilhar perfis privados, tokens, payloads pessoais ou backups Make no Git.
