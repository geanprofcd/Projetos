# Publicação inicial do VENDRA original - 16/10/2026

URL: https://vendra-original-production.up.railway.app/login
Projeto: https://railway.com/project/caad2a82-373d-441c-8403-f3a7903a264f
Serviço vendra-original: 6279f29b-4264-4165-aada-95c260685fa6
Production: d4a67a07-5075-4b3a-82bd-338d50126d3f
Deploy/build Linux: 3948ab61-9a52-45de-a4cb-aaa0bf41152d

## Executado

- Release enviada diretamente ao Railway privado, sem publicar o código original privado no GitHub. 122 arquivos app conferidos iguais ao original, inclusive templates/CSS/design.
- Cinco arquivos de hospedagem aplicados na pasta original: Dockerfile, .dockerignore, railway.json, requirements.production.txt e tools/production_start.py. .env, runtime, estado local e venv preservados. Backup de referência: output/backups/hosting-original-20261016-091013 na cópia Windows de acompanhamento.
- Variáveis privadas reais de produção configuradas no Railway; DEMO_MODE=false e COOKIE_SECURE=true. Chaves, token, senhas e sessões não integram este documento/pacote.
- Primeiro administrador original criado conforme autorização. Silas cadastrado como Comercial pelo portal HTTPS, com CSRF e auditoria; sem permissão para gerenciar usuários. Contas reais, não CODEX.
- SQL19 autorizado, CRUD/RLS/ACL validados no STAGING em transação revertida, depois aplicado no original. Migration vendra_original_legacy_ui_compatibility: farms (unidades/locais), crops e categories, vazias/RLS/acesso backend. Corrige PGRST205 das telas originais sem alterá-las. SQL20 reversão preparada, não executada; aborta se houver dados.

## Evidência funcional hospedada

23 verificações passaram: health real, login/logout, cookies Secure/HttpOnly/SameSite, bloqueio sem sessão, nove páginas essenciais, gravação e leitura de cliente/atendimento/nota interna e persistência dos três após reinício do mesmo deploy. Registros exclusivos CODEX-HOST e auditorias próprias limpos depois da validação; contas reais preservadas. Login comercial Silas e oito verificações de acesso/bloqueio aprovados. 24 tabelas públicas com RLS e SELECT negado a anon/authenticated; backend autorizado. Nenhum WhatsApp enviado nesta validação.

NÃO declarar homologação total: integrações Make/WhatsApp/IA continuam no STAGING e dependem de promoção seletiva/configuração/callbacks de produção e teste real. SMTP/convites, anexos em produção, importação/lote e recuperação completa não foram homologados por esta publicação. Contas CODEX STAGING permanecem para limpeza no final da homologação total. Original não recebeu snapshot nem dados STAGING.

## Endereço e operação

Usuário decidiu manter Railway por enquanto; nenhuma compra/domínio próprio/upgrade feito. Conta em trial: disponibilidade contínua depende do saldo/prazo do Railway; não foi contratado plano recorrente. Domínio atual usa HTTPS. Um domínio próprio poderá ser conectado posteriormente sem trocar o sistema.

Não há comandos pendentes para entrar. Comandos de manutenção, somente com token privado carregado no ambiente e CLI oficial:

```powershell
railway deployment list --project caad2a82-373d-441c-8403-f3a7903a264f --environment production --service vendra-original --limit 1 --json
railway logs --project caad2a82-373d-441c-8403-f3a7903a264f --environment production --service vendra-original --lines 30
railway restart --project caad2a82-373d-441c-8403-f3a7903a264f --environment production --service vendra-original --yes
Invoke-RestMethod https://vendra-original-production.up.railway.app/health
```

Atualizar somente a release limpa conferida; nunca enviar a pasta de trabalho com .env/estado:

```powershell
railway up . --path-as-root --project caad2a82-373d-441c-8403-f3a7903a264f --environment production --service vendra-original --detach
```

Startup local de produção é opcional, exige variáveis privadas do original já carregadas e porta livre; não aponta a STAGING:

```powershell
python -X utf8 -m tools.production_start
```

railway.json continua aceito nesta publicação; a CLI informou migração futura do formato antes de 01/12/2026. Não é motivo para refazer a aplicação agora. Próxima etapa concreta: promoção seletiva da integração homologada STAGING para a produção, reconciliando SQL/Make/configuração e preservando o design. Não religar disparos automaticamente.

## Integração original hospedada e conversas liberadas - 16/10/2026
SQL21 original autorizado/aplicado, dez callbacks Make migrados para Railway; IA e texto humano reais concluíram com WAMID, tentativa única e READ. Após autorização explícita, IA e respostas humanas estão ligadas para clientes reais. Não dependem de túnel/Windows. Disparo individual preparado, envio ainda bloqueado, autorização de teste temporário solicitada. Importação/lote/mídia ficam posteriores. Ler docs/OPERACAO_ORIGINAL_ONLINE.md para evidências, limites, comandos e pendências atuais; checkpoints anteriores descrevem o estado histórico, não o atual.

