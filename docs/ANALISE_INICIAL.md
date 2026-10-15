# Análise inicial do VENDRA

Atualização: o bloqueio do módulo ausente foi resolvido após publicação, e a rede do Drive passou a funcionar. Consulte `VALIDACAO_POS_PUBLICACAO.md` para o estado atual; os resultados abaixo preservam a análise inicial.

Registro de continuidade de 14/10/2026, baseado no PDF enviado, nos ZIPs e nos dois blueprints do Make. O arquivo do link do Google Drive não foi lido: o proxy retornou HTTP 403 ao tentar acessá-lo.

## Produto e regras centrais

VENDRA é um produto independente do Plantar. A primeira fase é CRM e atendimento híbrido IA/humano; estoque, financeiro, faturamento, compras e ERP completo são evolução futura, não funcionalidades homologadas desta base.

O cliente concentra atendimentos e histórico. Um atendimento comercial pode ter uma oportunidade vinculada a funil, etapa, responsável e itens de produtos/serviços. O valor da oportunidade é calculado pela soma de quantidade × preço negociado dos itens; snapshots preservam a negociação. Ganho/perda comercial não equivale a faturamento.

O catálogo, os funis, as oportunidades, os atendimentos, as configurações de integração, a auditoria e os indicadores estão separados por serviços. Os dados demo ainda contêm exemplos agronômicos herdados; a documentação prevê identidade própria e eliminação da dependência desse domínio.

## Arquitetura observada no código

| Camada | Implementação |
| --- | --- |
| HTTP e renderização | FastAPI, rotas em `app/routers`, Jinja2 em `app/templates` |
| Interface | CSS e JavaScript versionados em `app/static` |
| Configuração | `app/core/config.py`, pydantic-settings, variáveis e `.env` |
| Dados reais | Cliente Supabase Auth público e cliente backend administrativo separados |
| Dados demo | Estruturas em memória com persistência local em `.vendra-data` |
| Autorização | Sessões, perfis, acesso por módulo/papel e CSRF em formulários |
| CRM de homologação | RPCs específicas de STAGING para operações atômicas |
| Mensageria principal | Webhooks, outbox, controle IA/humano, janela WhatsApp e status WAMID |

`app.main:app` é a aplicação principal, incluindo integrações externas. `app.staging_h1_005b9:app` é uma aplicação restrita: clientes, usuários, atendimentos internos, CRM, prévia, simulações, prontidão e contrato. Não monta as rotas externas de Make/Meta.

No STAGING, o guard exige projeto Supabase indicado por `VENDRA_STAGING_REF`, URL raiz correspondente, `APP_ENV=staging`, `DEMO_MODE=false` e credenciais distintas. Ele bloqueia configuração ativa de Make, Meta e SMTP. Conectar a camada de mensageria exigirá um fluxo separado compatível com esse desenho; inserir um segredo do Make no STAGING atual impediria sua inicialização.

## Reconstrução das versões

Foram recebidos 19 ZIPs, correspondentes a 14 conteúdos únicos. Cinco são duplicatas idênticas por SHA-256. Os manifestos e listas de hashes disponíveis foram verificados sem divergências. A base contém 210 arquivos, mas ainda falta um módulo local exigido por imports; o nome do ZIP não estabelece completude.

Sequência importada:

1. `VENDRA_BASE_H1_005B8`: na prática contém o estado de código até B7 e `version.json` 0.0.25.
2. `H1_005B8_CONTRATO_ISOLADO`: acrescenta contratos, eventos e RPCs simulados.
3. `H1_005B9_UX_GOVERNANCA_SEM_ENVIO`: PRG, prontidão via fetch e controles de cache.
4. `H1_005B9_HOTFIX_FEEDBACK_F5`: feedback de confirmação exibido uma única vez.
5. `H1_005B9_HOTFIX_CONFLITO_VERSAO`: mensagens específicas de conflito/estado/permissão.
6. `H1_005B9_HOTFIX_PT409`: tratamento PT409 no contrato e SQL corretivo correspondente.
7. `H1_005B9_HOTFIX_PT409_CRM_SIMULACOES`: tratamento PT409 nos routers de CRM e simulação e SQL corretivo legado.

A correção de testes B3 já está na base. Reaplicar B2–B7 por cima da sequência final restauraria entrypoints e templates antigos, por isso esses pacotes foram mantidos como referências fora do checkout. O arquivo `docs/IMPORTACAO.json` registra o pacote e SHA-256 final de cada um dos 234 arquivos importados.

## Evidência documental e evidência desta máquina

O adendo final do mestre v1.28 relata homologação anterior de B8 no Windows/Supabase, incluindo concorrência real, idempotência e limites de tentativa. Isso é histórico informado no documento, não validação reproduzida aqui.

O mestre propõe B9; os ZIPs fornecem sua implementação e hotfixes posteriores. Portanto, o código recebido está além do último marco descrito no PDF. Ainda é necessário registrar as evidências funcionais desses patches no projeto Supabase correto.

A inicialização local da aplicação principal falhou com `ModuleNotFoundError: app.services.local_credentials_service`. Esse arquivo é necessário mesmo antes de avaliar credenciais externas. Os testes de serviço e verificações de fonte que passaram não compensam a ausência de autenticação executável.

## Pontos concretos para o próximo desenvolvimento

- Recuperar a base completa ou o módulo original `local_credentials_service.py`. Não presumir que um stub implementa corretamente gestão e armazenamento de credenciais locais.
- Reexecutar os cinco módulos bloqueados e validar login e um fluxo funcional após recuperar o arquivo.
- Conferir schema e RPCs no Supabase-STAGING antes de aplicar qualquer SQL. Há arquivos candidatos em `sql/drafts`; eles não provam que o schema remoto está atualizado.
- Confirmar os hotfixes PT409 no banco antes de ensaiar conflitos de versão reais.
- A função principal `dispatch_service.create_dispatch` recusa `DEMO_MODE=false`, com indicação de que o fluxo real ainda depende da camada de migration. Conectar o Make sozinho não resolve essa limitação.
- A saúde do STAGING declara modo Supabase e ausência de envios, mas não consulta o banco. Um HTTP 200 em `/health` não seria prova de conexão funcional.
- Selecionar endereço HTTPS de implantação para receber callbacks do Make; os blueprints apontam para um túnel temporário. A interface de onboarding não fornece preview público localhost.

Não foram feitas mudanças na lógica da aplicação, nos testes, nas dependências declaradas ou nos scripts SQL recebidos. Não houve commit, push, execução SQL remota ou publicação do ambiente.
