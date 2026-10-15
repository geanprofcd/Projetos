# H1-006E — agente, callbacks e saída controlada

15/10/2026, Brasília. Complementa o checkpoint histórico PONTO_DE_RETOMADA_H1_006E.md. Desenvolvido/executado no Windows STAGING; nenhum arquivo promovido ao original.

## Resultado

Rota normal da cópia REV9 comprovada: entrada nova → controle IA → arquivos/Knowledge → agente → resposta persistida → outbox. Um envio real posterior ao único destinatário autorizado executou o módulo WhatsApp e vinculou seu WAMID. Evento real delivered recebido no Make foi copiado para a ponte diagnóstica e persistido. Isso não homologa recepção contínua na cópia nem status automático no desenho final: a cópia é sob demanda e os túneis anteriores expiraram. Leitura real desse envio ainda não comprovada.

## Evidências

| Caso | Evidência | Resultado |
|---|---|---|
| Agente e Knowledge isolados | 8eb089e933d54fd690f2815ef227555f | Agente e consulta executados, sem resposta/outbox/envio |
| Contratos HTTP com Supabase real | ferramenta local, relatório privado | 18 verificações aprovadas; preparação, token, duplicatas, conflitos, handoff e reconciliação; fixtures removidas |
| Seis callbacks Make/HTTPS | vínculo 378fa2acd1844836b30590053f5d4d6d | Supressão 202; delivered/read sintéticos; token errado 403; vínculo reconcilia 2; repetição 0; fixture removida |
| Rota normal sem envio | fa51655943774d4e8255e8e8e9617a07 | 71/64/8/21/2/78/20/67/99; uma resposta IA e outbox claimed, marcador técnico removido |
| Replay exato | d2d6408a47cb4bb5ba53b454d35caf03 | Só 71/64/99; sem agente/envio e sem duplicar entrada |
| Nova entrada após handoff | a9bd4f21649142739f6524d9ee21051e | Só 71/64/99; mensagem persistida, modo human versão 3 e zero outbox na fixture |
| Tentativa com comparação de telefone inadequada | 0255770040b942a3b57da5ffae4b7ce2 | Resposta autorizada; filtro de teste comparava 12 com 13 dígitos equivalentes e bloqueou a saída; nenhuma mensagem enviada |
| Envio real controlado corrigido | 24df24dec9524938a7505d492863b969 | Agente/Knowledge, 67, WhatsApp 75 e vínculo 80 executados; uma saída com WAMID vinculado |
| Evento Meta real delivered | original 115e19f570bb477b99166eaaf6946fb9; cópia e9ed18e094314d929be69aa5242d9a59 | WAMID conferido; HTTP 202 e status delivered persistido, sem novo envio |

188 testes Windows de regressão aprovados em cópia limpa (1,221 s), além dos 31 focados previamente aprovados. Nenhuma aplicação Python foi alterada depois dessa suíte nesta rodada; a entrega acrescenta a ferramenta de diagnóstico já exercitada e este registro. Não repetir testes idênticos sem mudança/falha que justifique.

## Ajustes e limites

- Túnel diagnóstico 8013 renovado dentro da autorização já dada. Todas as URLs HTTP das duas cópias atualizadas; original REV9 e Disparo Inicial sem novas edições. A ponte 8012 não foi redirecionada.
- Teste sintético executado com perfil temporário 8013 reduzido exclusivamente ao telefone da fixture. Perfil diagnóstico original restaurado depois. Flag global temporária identificada removida; fixtures sintéticas eliminadas, mensagem real anterior preservada.
- A revisão automática recusou uma tentativa de replay por limite de uso; nenhuma execução ocorreu naquela tentativa. Após o usuário orientar a continuar, o encerramento foi autorizado. Nova fixture permitiu concluir replay/handoff. Outro replay falhou por hostname expirado; passou após renovar o túnel. Não mascarar essas falhas como aprovação na primeira tentativa.
- Para o envio real, foi criado atendimento exclusivo CODEX-SEND, sem alterar o atendimento real anterior. A liberação na cópia exigiu simultaneamente entrada única, destinatário exato e autorização/política da outbox. Variante BR de 13 dígitos conferida como equivalente ao destinatário autorizado; tentativa anterior sem envio cancelada no banco.
- Filtros constantes de bloqueio restaurados após o teste; cópias 6639761/6640168 inativas, flag global removida, atendimento CODEX-SEND encerrado em modo humano. Evidências do envio real preservadas no STAGING. Não excluir contas CODEX antes da homologação total.
- Status reais sent/delivered chegaram ao original. O HTTP do original tinha destino temporário indisponível; copiar os payloads reais para o auxiliar permitiu persistir o status, sem substituir/redirecionar o original. Não equivale a callback contínuo automático homologado na cópia.
- O retorno histórico execution_mode=STAGING_COPY_NO_SEND era constante, inclusive no teste pontualmente autorizado. O comprovante de envio é a execução dos módulos 75/80, WAMID e evento Meta real; não inferir ausência de envio somente desse rótulo.

## Plano acelerado por marcos

1. **Integração sem envio — comprovada nesta rodada:** agente/Knowledge, resposta/outbox, replay e handoff. Contratos negativos e concorrência aproveitam evidências anteriores válidas.
2. **Saída e Disparo Inicial — em conclusão:** saída real REV9 com delivered já comprovada; falta leitura se aplicável, recepção contínua isolada e cópia do Disparo Inicial com template/normalização e registro completo. Auditoria do Disparo Inicial confirmou conexão Israel/template existente, porém callback antigo /disparos/{dispatch_id}/status exige contrato próprio; não apontar cegamente para callback de outbox.
3. **Homologação final e promoção seletiva:** infraestrutura estável de recepção/HTTPS, recuperação operacional, regressão pertinente, backups/manifesto/rollback, aplicação somente do conjunto homologado no original e limpeza final de contas/auxiliares. Hospedagem permanente ainda não definida.

Agrupar testes independentes por marco, corrigir falhas e repetir somente o necessário. Não pedir ao usuário para executar comandos já autorizados. Documento Mestre atualizado uma vez por entrega consolidada. Velocidade não altera os requisitos de isolamento nem transforma testes simulados em entrega Meta real.

## Operação da ferramenta

Executar como módulo a partir da raiz do runtime STAGING preparado; não executar o arquivo diretamente porque o import app depende da raiz no caminho Python. Perfil e resposta de teste são privados e não acompanham o ZIP.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.whatsapp_callbacks_contract_check --config 'CAMINHO_PRIVADO_DO_PERFIL_8012' --resposta-agente 'CAMINHO_PRIVADO_DA_RESPOSTA.txt' --relatorio 'CAMINHO_PRIVADO_DO_RELATORIO.json'
```

Sem --executar apenas confere pré-condições. Acrescentar --executar cria fixtures e flag global temporária no projeto STAGING fixado pela ferramenta e remove seus registros ao terminar. Antes de repetir, conferir isolamento dos consumidores públicos: a ponte 8012 deve continuar IA/envio false e a ponte diagnóstica/consumidores não devem atender dados reais com a flag temporária ligada. TestClient não abre porta e não envia WhatsApp. Guardar o relatório; falha de limpeza exige conciliação por IDs, nunca exclusão genérica.

O instalador do pacote é dry-run por padrão e inclui backup ao aplicar; não executa SQL, inicia processo/túnel, altera Make ou envia mensagens. Não há motivo para reaplicar agora no runtime desta sessão, onde os arquivos já estão presentes.

## Links

- [Fonte STAGING](https://github.com/geanprofcd/Projetos/tree/desenvolvimento/vendra-staging)
- [Cópia REV9](https://us2.make.com/292724/scenarios/6639761/edit)
- [Fluxo normal](https://us2.make.com/292724/scenarios/6639761/logs/fa51655943774d4e8255e8e8e9617a07)
- [Envio real e vínculo](https://us2.make.com/292724/scenarios/6639761/logs/24df24dec9524938a7505d492863b969)
- [Evento delivered persistido](https://us2.make.com/292724/scenarios/6640168/logs/e9ed18e094314d929be69aa5242d9a59)

Próxima ação: implementar e exercitar a cópia isolada do Disparo Inicial com seu contrato de registro; resolver recepção contínua antes de declarar o fluxo integral homologado. Original preservado.
