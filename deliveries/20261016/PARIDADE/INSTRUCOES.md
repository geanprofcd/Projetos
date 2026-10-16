# Paridade e convites por link

Original Windows e Railway ja atualizados; nao precisa reaplicar. Quatro arquivos de convites promovidos com backup. Layout/base/CSS preservados; o aviso existente mostra um campo para copiar o convite. Bucket privado ticket-attachments criado e validado no banco ORIGINAL, sem policy nova; o pacote nao cria bucket nem modifica SQL/Make ou dados automaticamente.

Convites: INVITATION_DELIVERY=link e PUBLIC_APP_URL=https://vendra-original-production.up.railway.app configurados no Railway. Link48h/usounico/hash no banco, sem SMTP. Perfil e delegacao preservados. 18 testes/13checks reais STAGING/9original; anexos9STAGING/10original;15paginasadmin200. Nao declarar midia WhatsApp integrada: transporte por item/WAMID e gestao Meta com token especifico continuam pendentes.

Em outra copia, extraia o ZIP e simule antes de aplicar:

```powershell
python -X utf8 aplicar.py --destino "C:\CAMINHO\vendra_starter"
python -X utf8 aplicar.py --destino "C:\CAMINHO\vendra_starter" --aplicar
```

Confere hashes e faz backup somente dos arquivos selecionados. Nao altera .env, estado, credenciais ou banco. Reinicie somente a instancia dessa copia conforme sua configuracao habitual. Teste opcional na pasta destino:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_user_invitation_link tests.test_ticket_attention tests.test_conversation_order
```

Para reverter, restaurar somente os arquivos do backup indicado e republicar release limpa, quando hospedada. Nao apagar bucket com dados reais; inventariar/exportar antes. Nenhum rollback SQL necessario. Detalhes em files/docs/PARIDADE_ORIGINAL_ONLINE_20261016.md.
