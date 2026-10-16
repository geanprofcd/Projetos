# VENDRA original - listas, quantidade e custos

Portal: https://vendra-original-production.up.railway.app/disparos

Entrega complementar ao pacote CONVERSAS_ORIGINAL. Oito arquivos já aplicados seletivamente na pasta original Windows desta máquina, com backup output/backups/listas-original-20261016. Railway e banco original já atualizados separadamente após autorização específica. Não reinstalar nem reaplicar SQL. Preservados .env, runtime, venv, estado, main/base/CSS. Credenciais e dados STAGING não integram o pacote.

Individual e listas liberados. Importe arquivo, confira contatos, informe quantidade e clique Enviar quantidade. A fila considera primeiros contatos prontos, exclui inválidos/duplicados e processa um por vez. Nenhuma importação inicia disparos sozinha. Custo Meta real por mensagem entregue. Limite20mil linhas não significa carga20mil homologada. Resultado incerto: conferir mesmo pedido antes de repetir.

O pacote é atualização seletiva para a base correspondente, não instalador completo. Em outra máquina, conferir hashes/base, fazer backup e aplicar somente arquivos listados; não copiar configurações ou estado STAGING. SQL23 foi aplicado no STAGING/original; SQL24 reversão preparada recusa apagar dados. Scripts SQL e Make são separados da cópia. Nenhum plano pago contratado por esta entrega.

Recalcular custos sem acessar provedores:

```powershell
python -X utf8 tools/calcular_custos_vendra.py --cambio 5.50
Invoke-RestMethod https://vendra-original-production.up.railway.app/callbacks/health
```

Documentação detalhada em files/docs. Não há comando necessário para usar o portal hospedado.
