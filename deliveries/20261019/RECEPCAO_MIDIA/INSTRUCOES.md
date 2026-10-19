# Recepcao de midia - v1.60 - SOMENTE STAGING

JA aplicado na copia Windows STAGING. Nao foi aplicado no original/Railway; nao promover este pacote ao principal. SQL32 autorizado/aplicado somente no STAGING. SQL33 e reversao preparada, nao executada. Instalar arquivos nao executa SQL nem altera Make/flags. Nunca pausar cenarios originais para testes.

52 testes Windows,18 verificacoes funcionais reais STAGING,4 arquivos proprios Meta->Make->STAGING com conteudo/hash conferidos e replay sem duplicacao. WAMIDs sinteticos; evento real do WhatsApp do usuario ainda pendente. Nao declarar recepcao continua ou producao homologadas.

Para outra COPIA STAGING, extraia o ZIP e simule primeiro:

```powershell
python -X utf8 aplicar.py --destino "C:/CAMINHO/COPIA_STAGING/vendra_starter"
python -X utf8 aplicar.py --destino "C:/CAMINHO/COPIA_STAGING/vendra_starter" --aplicar
```

Instalador confere hashes e faz backup apenas dos arquivos selecionados. Recusa aplicacao se os perfis locais apontarem ao Supabase original. Nao copia credenciais, estado ou modelos demonstrativos. A flag VENDRA_BRIDGE_INBOUND_MEDIA_ENABLED continua false por padrao; habilitar somente no destino autorizado com contrato completo.

Teste local, sem WhatsApp:

```powershell
./.venv/Scripts/python.exe -X utf8 -m unittest tests.test_whatsapp_inbound_media tests.test_whatsapp_callbacks tests.test_whatsapp_human_bridge tests.test_hosted_callbacks tests.test_whatsapp_media
```

Reversao STAGING: desabilitar somente a nova rota/ramo de midia, restaurar backend seletivo do backup; avaliar SQL33 separado. Nao remover RPC em uso, mensagens/anexos reais nem restaurar snapshot inteiro. Novo arquivo whatsapp_inbound_media.py deve sair somente depois de reverter consumidores. Detalhes em files/docs/VALIDACAO_RECEPCAO_MIDIA_20261019.md.
