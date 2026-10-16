# Listas e disparos originais liberados - 16/10/2026

Portal: https://vendra-original-production.up.railway.app/disparos

## Executado e autorizado

Disparo individual regular liberado expressamente para clientes reais: restrição temporária de telefone removida do Railway e dos filtros Make, preservando segredo próprio, telefone BR válido, reserva e política de template. Canal dispatch_bridge/dispatches ligado. Não foi feito outro disparo individual para repetir o teste já encerrado.

Listas: SQL23 aplicado primeiro no STAGING, depois no original após autorização específica. Duas tabelas, quatro funções SECURITY INVOKER, RLS e acesso exclusivo service_role. Migration vendra_dispatch_lists_persistence_v1; ajuste de retomada vendra_dispatch_lists_resume_v1. SQL24 é reversão preparada, não executada; aborta quando existem dados. Nenhuma tabela/dado STAGING foi copiado.

Backend da lista persiste contatos e seleciona a quantidade pedida em transação. O UUID de cada item é a chave idempotente do pedido. Reservas usam SKIP LOCKED. Invalidos/duplicados não são enfileirados. A fila hospedada processa um contato por vez, no máximo uma tentativa de transporte por reserva; resultados incertos permanecem para conferência, sem reenvio cego. Contatos ainda na fila permanecem no banco após reinícios. Reservas já confirmadas são reconciliadas sem selecionar o mesmo contato novamente. Não foi alegada restauração integral de banco nem teste de carga de20mil envios.

O worker só funciona com DISPATCH_LISTS_ENABLED e dispatch_lists.enabled, mais canal individual ativo. Fila vazia: consulta leve e intervalo15s; havendo trabalho, intervalo mínimo1s entre iterações. Uma nova fila pode levar até15s para começar. Nenhuma lista é iniciada automaticamente por ativar o recurso ou importar arquivo.

Design comercial preservado. Campo Quantidade e botão Enviar quantidade inseridos na área de fila existente; confirmação do navegador usa o número escolhido. CSS/base/main originais preservados. Upload máximo12MB e20mil linhas, sujeito à capacidade e aos limites dos provedores; limite de arquivo não é comprovação de carga homologada nesse volume.

## Evidências relevantes

- SQL transacional STAGING revertido: quantidade1de2, clique repetido, quantidade inválida, inválido excluído, ACL/RLS, reserva única, vínculo, ausência de outbox no teste SQL e retomada sem selecionar novamente confirmado.
- 36 testes dos contratos afetados passaram; conferência de sintaxe JavaScript aprovada. Não somar as suítes repetidas como funcionalidades novas.
- 14 verificações HTTP com banco real STAGING: login Comercial, upload, duas linhas prontas/uma duplicada/uma inválida, quantidade zero422, seleção1, clique repetido, um pedido e progresso autenticado. Transporte suprimido nessa rodada; fixtures próprias limpas e configurações restauradas.
- Rodada funcional separada STAGING: lista3linhas/1pronto/1duplicado/1inválido, quantidade1, worker automático, um template Meta e WAMID vinculado, status sent. Make6661208 execução de9b565ab0fa4aa8870b9e2687e50b0b, quatro módulos/um Send. Evidência real preservada; não afirmar delivered/read dessa rodada. Cenário STAGING voltou a inativo e filtro de envio constantefalse.
- Original hospedado: login com a nova senha administrativa, upload real,2prontos/1duplicado/1inválido, campo e confirmação de quantidade, quantidadezero422, progresso autenticado, zero pedidos/WhatsApp gerados. Lista CODEX-HOST própria removida. Não repetir provider test já aprovado no STAGING.
- Deploy final original:8bd7be32-dcf6-48dc-969d-a65c0ee24562 SUCCESS, release privada, sem exposição integral do código original no GitHub público.

## Usar agora

1. Abra Disparos no portal. Para envio individual, preencha nome e telefone e clique Disparar.
2. Para lista, importe arquivo, confira contatos prontos/invalidos/duplicados.
3. Informe a quantidade de contatos prontos que deseja enviar e clique Enviar quantidade. O sistema escolhe os primeiros prontos na ordem da lista.
4. Confirme o número no aviso do navegador e acompanhe progresso/histórico. Não repita pedidos pendentes de confirmação sem conferir o mesmo registro.

Custos: docs/CUSTOS_VENDRA_20261016.md. Estimativa de volume não ativa campanhas nem garante que todos os contatos receberão a mensagem. Tarifas Meta por mensagem entregue; falhas/repetições também podem consumir Make. Nenhuma compra, upgrade ou domínio contratado.

## Comandos

```powershell
python -X utf8 tools/calcular_custos_vendra.py --cambio 5.50
Invoke-RestMethod https://vendra-original-production.up.railway.app/callbacks/health
```

Não há instalação ou comando necessário para usar o portal hospedado. SQL e Make já aplicados separadamente; não reaplicar por receber o pacote. CODEX permanece até encerramento do escopo de homologação acordado. Mídia/SMTP e melhorias futuras não bloqueiam os disparos liberados.
