# VENDRA - regras pela etapa atual v3

Ja aplicado no STAGING e banco original; nao ha instalacao/deploy/SQL pendente para usar o portal:
https://vendra-original-production.up.railway.app/atendimentos?view=funil

Novo Lead recebe resposta -> Qualificacao, mesmo com historico. Resposta depois do disparo liga IA antes do Make, respeitando pausa manual atual. Qualificacao envia Calendly confirmado com WAMID -> Proposta, sem esperar delivered/read. Novo Lead nao pula diretamente para Proposta.

Entrega exclusivamente SQL/documentacao: nenhuma alteracao de app/design/.env/runtime/estado. SQL28 altera quatro funcoes existentes; SQL29 e reversao para a regra anterior, nao executar automaticamente. Script de reconciliacao ja executado:5cards e1IA; backup privado/auditoria preservados. Nao repetir campanhas/perguntas antigas para testar.

Nao reaplicar SQL26 da revisao anterior, nem executar SQL28/reconciliacao/rollback por copiar os arquivos. Scripts SQL e Make sao operacoes separadas. Em outra instalacao, revisar projeto/destino/estado e fazer backup antes de qualquer aplicacao. Reverter funcoes nao reverte automaticamente os dados dos cards.

Matriz SQL revertida e11verificacoes HTTP/SDK STAGING aprovadas com historico e novo ciclo; WAMIDs sinteticos nao comprovam entrega real. Nova mensagem real foi solicitada para validacao pelo Make e ainda nao estava confirmada ao gerar este pacote. Nenhuma mensagem enviada nesta correcao.

Comando opcional de verificacao, sem envio:
```powershell
Invoke-RestMethod https://vendra-original-production.up.railway.app/health
```

Detalhes em files/docs/CORRECAO_REGRAS_POR_ETAPA_20261016.md. Fonte/manifesto com hashes e referencias; sem credenciais ou dados de clientes.
