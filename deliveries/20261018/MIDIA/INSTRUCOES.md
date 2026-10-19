# Midias WhatsApp - v1.59

Original Windows e Railway JA atualizados seletivamente, sem necessidade de reaplicar. SQL30 ja aplicado nos dois bancos; SQL31 e reversao NAO executada. Este instalador apenas copia arquivos, nunca executa SQL, altera flags ou envia mensagens. Design/.env/estado preservados. Tres cenarios Make originais ativos; nao pausar para testes.

46 testes Windows e16 checks funcionais STAGING; quatro formatos reais aceitos Meta no STAGING, um PDF delivered no original. Envio liberado para clientes reais apos autorizacao especifica. Recebimento de midias ainda pendente. Janela, perfil e reserva obrigatorios; resultado incerto exige revisao sem reenvio automatico.

Em outra copia, extraia e simule primeiro:

```powershell
python -X utf8 aplicar.py --destino "C:/CAMINHO/vendra_starter"
python -X utf8 aplicar.py --destino "C:/CAMINHO/vendra_starter" --aplicar
```

Teste opcional no destino:

```powershell
./.venv/Scripts/python.exe -X utf8 -m unittest tests.test_whatsapp_media tests.test_whatsapp_human_bridge tests.test_whatsapp_human_command tests.test_hosted_callbacks tests.test_outbox_wake_guard tests.test_ticket_attention
```

Backup seletivo automatico antes da copia. Para reversao em servidor, coordenar Make e flags primeiro, restaurar arquivos do backup e so depois avaliar SQL31; nao remover RPCs em uso ou dados reais. Nao restaurar telefone fixo de teste. Arquivo novo whatsapp_media_service.py so deve ser retirado apos reverter seus consumidores. Nenhum segredo e distribuido. Detalhes em files/docs/VALIDACAO_MIDIA_WHATSAPP_20261016.md.
