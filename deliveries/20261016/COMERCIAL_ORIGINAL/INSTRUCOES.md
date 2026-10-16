# VENDRA original - funil e regras comerciais

Portal: https://vendra-original-production.up.railway.app/atendimentos?view=funil

Ja aplicado no original Windows e no Railway apos homologacao STAGING. Nenhum comando e necessario para usar o portal. Este pacote e complementar e seletivo, nao e um instalador completo. Preserve .env, runtime, .vendra-data, venv e alteracoes locais. Segredos, clientes, sessoes e a fonte privada completa nao integram a entrega.

Contem seis arquivos completos compartilhados de backend e o aplicador de duas funcoes do ticket_service privado. Nao substituir ticket_service inteiro pelo STAGING. Em outra maquina, conferir a base e hashes, fazer backup dos destinos, copiar somente os seis arquivos app listados no manifesto e aplicar as duas funcoes com o comando abaixo. O programa faz previa por padrao e guarda .bak ao aplicar.

```powershell
python -X utf8 files/tools/aplicar_ordem_comercial_original.py --target "CAMINHO_DO_ORIGINAL/app/services/ticket_service.py"
python -X utf8 files/tools/aplicar_ordem_comercial_original.py --target "CAMINHO_DO_ORIGINAL/app/services/ticket_service.py" --apply
Invoke-RestMethod https://vendra-original-production.up.railway.app/health
```

SQL25/26 ja executados no projeto correto. SQL27 apenas reversao, nunca automatica: reverter antes o codigo de ordenacao, preservar dados/evidencias e revisar definicoes atuais. Copiar arquivos nao executa nem autoriza SQL/Make. Make6534261 filtro8 route_to_ai=true ja ajustado; demais filtros e conexoes preservados. Nenhuma campanha iniciada.

Backups nativos: output/backups/http-original-20261016 e output/backups/regras-comerciais-original-20261016 na copia de acompanhamento. Configuracao anterior dos funis preservada privadamente. Recuperacao seletiva de codigo nao equivale a restauracao integral de banco.

Primeira resposta qualifica e liga IA antes do Make; pausa manual prevalece. Calendly avanca para Proposta na primeira entrega/leitura confirmada pela Meta. Lista/quadro priorizam ultima recebida e recencia. Testes e limites detalhados em files/docs/VALIDACAO_FUNIS_COMERCIAL_20261016.md. Calendly foi validado por eventos sinteticos em transacao revertida; nao declarar novo envio real Meta.
