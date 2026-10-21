# VENDRA v1.65 — feedback da importação e carga de listas

Interface homologada: nome selecionado, círculo durante upload/processamento, arquivo confirmado no mesmo local e persistência após refresh. 18 checks navegador local com HTTP controlado +9 HTTP/SDK reais STAGING +8 testes existentes. Carga STAGING:20.000 contatos, leitura completa e8 inícios concorrentes da mesma fila sem duplicação;10 verificações, zero envios, fixtures removidas.

APLICADO ao original Windows e release privada SOMENTE o template e dois assets. Backup output/backups/upload-lista-original-20261021. Configurações, backend, SQL e Make preservados. PUBLICAÇÃO ONLINE PENDENTE: Railway recusou CLI/consulta e informa incidente de API/builds pausados https://status.railway.com/incident/QH8L8B3E. Login/health original200; não declarar interface nova já hospedada. Nenhuma credencial foi substituída.

Pacote opcional apenas para OUTRA COPIA STAGING; não contém .env, credenciais, clientes, SQL novo ou código do VENDAXIS. Não usar para substituir o original inteiro. O instalador não publica serviços nem inicia filas.

```powershell
python -X utf8 aplicar.py --destino "C:/CAMINHO/COPIA_STAGING/vendra_starter"
python -X utf8 aplicar.py --destino "C:/CAMINHO/COPIA_STAGING/vendra_starter" --aplicar
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_dispatch_lists
```

Publicação futura somente na RELEASE PRIVADA vinculada ao VENDRA original, após normalização Railway:

```powershell
railway up --service vendra-original --environment production --detach --message "Feedback visual de importacao homologado"
railway deployment list --service vendra-original --environment production --json
```

Confirmar SUCCESS, login, assets, nome da lista existente e estados da área antes de chamar online. Não repetir envios ou iniciar campanha para validar a interface. Reverter restaurando somente os arquivos do backup e removendo os assets novos da release, publicando a revisão conferida. Nunca pausar Make ou alterar variáveis/banco como efeito desta entrega.

Evidência e limites: files/docs/VALIDACAO_IMPORTACAO_LISTAS_20261021.md. Mestre v1.65 com237 páginas nas pastas Downloads/Automações e Downloads. Nenhum teste20k de entregas ou processamento prolongado alegado. VENDAXIS permanece separado e somente local.
