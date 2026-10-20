# VENDRA v1.61 — Recepcao e funis com 10.000 cards

Pacote de fontes para STAGING; instalador recusa destino com banco original. Nenhum SQL/Make/flag e executado automaticamente.

APLICADO: recepcao de midia no original, SQL32 privado e ramo85/86 do REV9 ativo, sem pausar outros cenarios. PDF real automatico validado no chat/download hospedado. Scroll interno simples sem barra vertical publicado com backup seletivo.

PAGINACAO: SQL34 aplicado somente no STAGING. 10.000 cards exclusivos,17 verificacoes reais Edge e74 testes Windows. Maximo120 cards por coluna no DOM; totais no banco, busca global do funil, movimentacao Comercial/versao/CSRF e foco preservados. HTML observado384538bytes/2554ms; nao e garantia de SLA ou de concorrencia. Fixtures removidas. SQL34 no original e sua flag aguardam autorizacao especifica.

Mestre1.61 cumulativo disponivel nas duas pastas Downloads solicitadas. Ver os relatorios em files/docs. Reversoes SQL33/35 separadas, nao aplicadas. Nao desativar cenarios originais ou apagar arquivos reais.

Para conferir/aplicar fontes em outra COPIA STAGING:

```powershell
python -X utf8 aplicar.py --destino "C:/CAMINHO/COPIA_STAGING/vendra_starter"
python -X utf8 aplicar.py --destino "C:/CAMINHO/COPIA_STAGING/vendra_starter" --aplicar
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_kanban_window tests.test_opportunity_bulk tests.test_conversation_order tests.test_ticket_attention
```

Ja executado autonomamente na copia desta sessao. Instalador confere hashes/faz backup seletivo. Nao copia .env, credenciais, sessoes, estado, dados de teste ou snapshot inteiro. KANBAN_WINDOW_ENABLED=false por padrao; ativar somente depois de SQL34 validado no destino autorizado. SQL34 nao transmite mensagens nem altera tabelas/RLS.

O pacote nao deve ser aplicado automaticamente no original: a publicacao dele usa um release privado seletivo, com backup, hashes e conferencias em ambiente hospedado. Para reverter, desligar somente a flag/ramo novo e restaurar seus arquivos, preservando texto/IA/status/disparos.
