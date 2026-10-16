# Calendly real no original - 16/10/2026

O usuario confirmou o envio da mensagem de teste solicitada. A rodada real fechou a pendencia Qualificacao -> resposta com Calendly -> Proposta. Nenhum replay, SQL adicional, deploy ou envio de teste iniciado pelo Codex.

## Evidencia correlacionada

- Entrada Meta em16/10/2026 18:14:25, horario Brasilia; execucao Make REV9 6534261 `ffdb0065f6dd420f9be2d168e4cdf168`, iniciada18:14:27.521. Sucesso,12.858s,9operacoes/9creditos.
- Modulo64 recebeu/persistiu e respondeuHTTP202, duplicate=false, automation.mode=ai, connected=true, route_to_ai=true, should_respond=true, make_instruction=CONTINUE_TO_AI, control_version=9. O filtro8 deixou a mensagem passar.
- Modulos71/64/8/21/2/24/69/76/81 executaram uma vez cada, zero erros. Modulo2 IA respondeu e modulo76 fez um unico envio; modulo81 confirmou o vinculo.
- Banco original: resposta externa de saida contem URL Calendly; outbox `6da0940e-91a2-4504-ac75-f2c866bd0d4e`, WAMID real presente, attempt_count=1, status=read; mensagem tambem read. WAMID completo e corpo da resposta permanecem privados no banco, nao neste documento.
- Historico real: Qualificacao -> Proposta em18:14:40.333927, source=system. IA permaneceu ai/versao9. A transicao ocorreu na confirmacao do envio; o callback de leitura veio depois.
- Callbacks de status Make d4e374ee242140aaaebc260afa631625 e ad85ad51645644b0b115ebe2b03787cf terminaram com sucesso. Prova terminal read correlacionada no banco.

Execucao: https://us2.make.com/292724/scenarios/6534261/logs/ffdb0065f6dd420f9be2d168e4cdf168

Portal: https://vendra-original-production.up.railway.app/atendimentos?view=funil

## Escopo e continuidade

Esta rodada partiu de Qualificacao e comprovou entrada real, passagem pelo filtro, IA, envio unico com Calendly, WAMID, Proposta e leitura, sem desligar a IA. Nao confundir com um novo teste real partindo de Novo Lead: essa transicao e a ativacao automatica por novo ciclo foram validadas na matriz SQL/HTTP STAGING e na reconciliacao documentada na v1.55.

SQL28 continua vigente; nenhum ajuste foi necessario apos esta rodada. Codigo original/Windows/configuracoes/design inalterados. Preservar mensagem real, outbox, auditoria e historico. Nao reaplicar scripts nem reenviar a pergunta para repetir o bloco aprovado. Nenhum comando pendente para usar o portal. Documento Mestre v1.56 registra esta evidencia; pacote v3 anterior permanece valido e inalterado.
