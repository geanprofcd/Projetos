# Alerta de atraso VENDRA

Original Windows e Railway ja atualizados; nao precisa reaplicar. Somente o servico de SLA mudou; teste e documento acompanham. Sem SQL, Make, credenciais, estado ou design. 14 testes e12HTTP/banco STAGING passaram; endpoint online200 e conversa real respondida fora dos alertas.

Em outra copia, extraia o ZIP, revise o caminho e simule primeiro:

```powershell
python -X utf8 aplicar.py --destino "C:\CAMINHO\vendra_starter"
python -X utf8 aplicar.py --destino "C:\CAMINHO\vendra_starter" --aplicar
```

O instalador confere hashes e salva backup dos arquivos existentes antes de substituir somente os selecionados. Reinicie apenas a instancia dessa copia conforme sua configuracao habitual. Na pasta de destino, verificacao opcional sem envio:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_ticket_attention tests.test_conversation_order
```

Reversao: restaurar somente os arquivos do backup indicado. Nenhum rollback SQL. A fila e os envios existentes nao sao modificados pelo instalador.
