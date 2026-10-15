# H1-006D | Concorrencia e copia isolada

Codigo aplicado na copia Windows STAGING e ponte 8012 reiniciada com perfil IA desligado. 188 testes de regressao, 31 focados e 21 verificacoes reais de concorrencia aprovados. Configuracao temporaria do banco restaurada; fixtures removidas e dados reais preservados. Nenhum SQL DDL ou envio externo nesta rodada.

Regra do usuario: tuneis/cenarios do original sao ambiente programado/testado; para STAGING copiar, nunca substituir. REV9 original permaneceu ativo e sem novas edicoes. Copia Make 6639761 criada sob demanda, sem webhook Meta, com tres envios bloqueados por filtro constante e terminando inativa. Teste de entrada ja persistida: HTTP 202/duplicate=true/route_to_ai=false; nenhum agente/provedor executado. Nao equivale a homologacao de webhook novo, resposta IA completa ou envio.

Codigo: https://github.com/geanprofcd/Projetos/tree/desenvolvimento/vendra-staging
Commit: https://github.com/geanprofcd/Projetos/commit/9846a55a7b318b3e5f051125345d8450aa72cd2b
Validacao: https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_CONCORRENCIA_COPIA_STAGING.md
Copia Make: https://us2.make.com/292724/scenarios/6639761/edit
Execucao: https://us2.make.com/292724/scenarios/6639761/logs/a0c7b553e7f24735819af848844325f5

Sincronizacao do checkout Git separado (executada pelo agente; comandos para consulta posterior):

```powershell
$repo = 'C:\Users\israe\Downloads\Automações\VENDRA-GIT-STAGING'
git -C $repo fetch origin
if (git -C $repo status --porcelain) { throw 'Preservar e revisar alteracoes locais' }
git -C $repo pull --ff-only
git -C $repo log -1 --oneline
```

Pacote de codigo separado: nao inclui segredos, perfis, backup Make ou payloads pessoais. Para outra copia STAGING preparada, extrair em pasta nova, conferir e aplicar somente depois da conferencia:

```powershell
Get-FileHash -LiteralPath '.\VENDRA_H1_006D_CONCORRENCIA_COPIA_STAGING_20261014.zip' -Algorithm SHA256
Expand-Archive -LiteralPath '.\VENDRA_H1_006D_CONCORRENCIA_COPIA_STAGING_20261014.zip' -DestinationPath '.\H1_006D_CONFERENCIA'
powershell -NoProfile -ExecutionPolicy Bypass -File '.\H1_006D_CONFERENCIA\tools\aplicar_callbacks_staging.ps1' -Destino 'CAMINHO_DA_COPIA_STAGING'
```

Ultimo comando e dry-run; -Aplicar faz backup e registra arquivos novos em rollback.json. Instalador nao executa SQL, reinicia processos, inicia tunel, altera Make ou envia mensagens. Rollback de codigo e manual a partir do backup, sem reverter dados/migrations. Nao e necessario reaplicar ou reiniciar agora na copia desta sessao ja atualizada.

Teste direcionado na copia runtime preparada:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_whatsapp_callbacks tests.test_whatsapp_control_bridge -v
```

A copia Make precisou regravar o descritor de consulta Knowledge no editor, mantendo o arquivo e a decisao pelo agente; primeiro run falhou antes de operar, reteste passou. Credenciais/configuracoes SaaS nao estao neste ZIP. Proxima etapa: rotas de resposta/vinculo na copia, agente/arquivos e handoff completo, depois envio de teste autorizado. Disparo Inicial requer copia propria. Principal nao promovido.
