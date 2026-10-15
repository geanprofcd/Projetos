# H1-006C: ponte e levantamento Git

14/10/2026, Brasilia. O Documento Mestre continua sendo a referencia de requisitos e decisoes. Git registra o codigo, os deltas e suas evidencias; publicacao nao equivale a instalacao ou homologacao funcional.

## Levantamento confirmado

O repositorio geanprofcd/Projetos e publico. Havia somente uma branch, entregas/staging-20261014, contendo pacotes ZIP/instrucoes, sem fontes extraidos. HEAD verificado: 4c8b5d8ad6b9e40443815bb108f4ad439c96727b. O pacote UTF8 publico possui blob Git 77110a38bc681b1dd8673d9e4b341ff95340a101 e SHA-256 0e7c4749d5d9da046686f1c0653968d5b163681912fda72108b6791cdb322203.

Comparacao com Windows: 246 arquivos payload, 244 identicos byte a byte, zero ausentes; duas diferencas em documentos de acompanhamento (AGENTS.md e docs/VALIDACAO_ATUAL.md). Fontes publicos identificam versao 0.0.25 com camadas STAGING H1-005B9/PT409. Nao assumir que a versao identifica por si so o conjunto homologado.

Base Git de desenvolvimento preparada a partir desse payload publico, acrescentando apenas os arquivos conhecidos das entregas H1-006A/B/C e documentacao tecnica. Codigo Go do launcher/updater e sql/migrations/003_private_attachments.sql encontrados somente no Windows ficam fora dessa incorporacao inicial: exigem levantamento proprio antes de integrar. Perfis .env, runtime, .vendra-data, sessoes, backups, executaveis e PDFs locais nao entram no commit. Documento Mestre permanece nas pastas solicitadas; sua versao/hash e resumida no checkpoint, sem publicar documentos internos indiscriminadamente.

Nao existe servidor de nuvem permanente identificado: usuario informou que a fonte de verdade era o Documento Mestre e orientou usar Git para o levantamento. Nao registrar sincronizacao com o antigo ambiente temporario como obrigacao ativa. Futuro servidor deve clonar a branch de desenvolvimento e aplicar uma revisao exata com configuracao propria.

## Codigo H1-006C

Ponte app.whatsapp_callbacks agora inclui vinculo autenticado da outbox, conferindo o telefone real no banco, token de reserva e IDs Meta. As rotas IA/control existem somente quando VENDRA_BRIDGE_AI_ENABLED=true no perfil explicito; padrao false. A RPC exige adicionalmente a configuracao global do banco, modo IA, versao valida, janela aberta e atendimento ativo. Nenhuma rota publica de troca de modo foi criada.

Duplicata de entrada nunca aciona novamente a IA. Texto base64 preserva Unicode/aspas; marcador tecnico final #1/#2/#3 e removido antes da preparacao. route_code e validado, mas esta etapa nao cria/atualiza oportunidade CRM; nao considerar essa parte homologada. Erros de permissao viram HTTP 403 sem diagnosticos privados. A ponte nao chama o provedor nem inicia worker.

## Validacao e estado

186 testes Windows passaram em copia limpa sem .venv na raiz de varredura (170 anteriores + 16 novos). 29 testes focados da ponte passaram. Sete verificacoes HTTP/SDK com Supabase STAGING real confirmaram controle global desligado, escopo da entidade, preparacao suprimida, versao divergente, saida inexistente recusada, nenhuma mensagem artificial e configuracao global ainda ausente. A instancia TestClient com contrato IA ligado nao foi publicada; banco/perfil de execucao mantidos desligados. Nao houve envio de mensagem ou SQL novo nesta etapa.

Codigo aplicado na copia Windows STAGING e ponte 8012 reiniciada com mesmo perfil. Make ainda usa apenas os contratos de entrada/status H1-006A; modulos de resposta/vinculo nao adaptados. Original 8010 e portal STAGING 8011 preservados. Concorrencia independente de preparacao, integracao Make de saida, passagem para humano em fluxo real e promocao seletiva continuam pendentes. Os 27 testes SQL da etapa B sao sequenciais/transacionais; nao substituem esses testes.

## Sincronizacao repetivel

Branch de codigo: desenvolvimento/vendra-staging. Branch de pacotes: entregas/staging-20261014. Clonar em pasta nova, sem transformar a pasta principal em destino de pull ou sobrepor dados locais:

```powershell
git clone --single-branch --branch desenvolvimento/vendra-staging https://github.com/geanprofcd/Projetos.git VENDRA-GIT-STAGING
git -C VENDRA-GIT-STAGING status --short
git -C VENDRA-GIT-STAGING log -1 --oneline
```

Atualizacoes futuras no checkout Git limpo:

```powershell
git -C VENDRA-GIT-STAGING fetch origin
git -C VENDRA-GIT-STAGING status --short
git -C VENDRA-GIT-STAGING pull --ff-only
```

Nao usar reset --hard nem clean para resolver divergencias: preservar mudancas e revisar o diff. Pull atualiza somente codigo; nao aplica migrations, muda Make ou transfere credenciais. Validar a mesma revisao no STAGING, registrar hash e evidencias no Documento Mestre e somente depois promover o conjunto homologado.

Teste local direcionado, usando o venv preparado da copia Windows:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_whatsapp_callbacks tests.test_whatsapp_control_bridge -v
```

O novo clone nao inclui venv, credenciais ou estado. Preparacao de runtime/hosting sera uma etapa propria; nao e necessario executar comandos agora na instalacao STAGING ja atualizada.
