# H1-006J - Conversas homologadas somente no STAGING

Código já aplicado na cópia Windows; 235 testes em cópia limpa e 14 verificações funcionais reais aprovados. Conversa WhatsApp, mensagem lida, botão administrativo, CSRF e conflito de versão validados. Não houve envio WhatsApp nesta etapa. Conta CODEX administrativa especificamente autorizada foi inativada e suas sessões revogadas; quatro contas CODEX aguardam limpeza ao final da homologação total.

O usuário determinou preservar integralmente estrutura UX/UI, design, layout e navegação do original. NÃO promover os templates, menus, CSS ou factories desta entrega ao original. Este pacote é exclusivo de testes. O backend aprovado deverá ser integrado aos controles comerciais existentes sem redesenho.

Railway tem somente conta autenticada e projeto VENDRA vazio, reservado para o original após homologação. Sem serviços, banco, credenciais, domínio comprado ou aplicação publicada. STAGING online somente se algum teste indispensável exigir.

Fonte: https://github.com/geanprofcd/Projetos/commit/3afccc4faed4d8eb524fc936a00a93a7bbe342f5
Validação: https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_CONVERSAS_STAGING_H1_006J.md
Tela local: http://127.0.0.1:8011/conversas

Nenhuma reinstalação manual necessária nesta sessão. Para outra cópia STAGING preparada, extraia em diretório novo e confira:

```powershell
Get-FileHash -LiteralPath '.\VENDRA_H1_006J_CONVERSAS_STAGING_20261015.zip' -Algorithm SHA256
Expand-Archive -LiteralPath '.\VENDRA_H1_006J_CONVERSAS_STAGING_20261015.zip' -DestinationPath '.\H1_006J_CONFERENCIA'
powershell -NoProfile -ExecutionPolicy Bypass -File '.\H1_006J_CONFERENCIA\tools\aplicar_callbacks_staging.ps1' -Destino 'CAMINHO_DA_COPIA_STAGING'
```

Último comando é somente dry-run. -Aplicar copia somente arquivos diferentes com backup e rollback.json. Não mexe em .env, estado, venv, sessões, SQL, Make, serviços ou hospedagem. Não instalar no original. A reversão restaura somente os arquivos registrados no backup, sem restaurar snapshot inteiro.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.dispatch_portal_start --config .env.h1_005b2 --check
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

Primeiro comando confere perfil, segundo executa regressão. Portal8011 já está em execução, transporte/worker desligados. Nenhuma promoção ao principal. Não contém segredos, perfis, WAMIDs, credenciais, banco local ou backups privados.

# H1-006J - Conversas e controle humano/IA homologados no STAGING

Em 15/10/2026 foi adicionada exclusivamente ao portal de testes a interface `/conversas`: lista das100 conversas WhatsApp mais recentes, histórico das100 mensagens mais recentes, responsabilidade humana/IA, confirmação de entrega/leitura e botão administrativo para assumir/retomar. Conteúdo renderizado com escape HTML; backend não entrega WAMIDs, tokens de reserva, credenciais ou telefones nessa tela. Históricos e estados reais são lidos do Supabase STAGING. Não há editor de mensagens nem envio direto novo nessa interface.

## Validação executada

- 17 novos testes de serviço/rota: restrição STAGING, demo bloqueado, UUID, perfil ativo/admin, modo/versão válidos, atendimento encerrado, conflito, janela de 24 h, automação global, confirmação RPC, CSRF, escape HTML e erros sem vazamento.
- Regressão completa em cópia limpa Windows: **235 testes aprovados em 2,311 s**, Python -X utf8. Relatório privado em VENDRA-validacoes/staging_20261015_134317_392_8cf95445/resultado.json. Nenhuma alteração de aplicação depois dessa execução.
- **14 verificações funcionais reais** UI/HTTP/SDK: botão Assumir clicado no navegador mudou o banco; login de administrador CODEX, leitura da resposta IA lida, no-store, CSRF, retomarIA,409 por formulário antigo, assumir com versão atual, Comercial lê/POSTbloqueado, conversa inexistente404, nenhuma outbox nova, Comum bloqueado na lista/detalhe/POST.
- Nenhum envio WhatsApp nesta etapa. Reutilizada a evidência real da H1-006I em atendimento exclusivo CODEX; as duas reservas canceladas permanecem visíveis como Cancelada, enquanto a única resposta transmitida aparece Lida.

A revisão automática exigiu autorização específica para conta CODEX administrativa; usuário concedeu somente STAGING. Auth criou o usuário sem perfil, então o mesmoID foi completado por upsert, sem duplicar conta. Conta CODEX-ATENDIMENTO-ADMIN inativada ao terminar, sessões revogadas, flag temporária removida e atendimento exclusivo novamente encerrado em modo humano. Sessão Comercial restaurada no navegador. Ledger privado contém4contas CODEX e foi conferido em modo somente leitura; nenhuma exclusão antecipada.

## Limite de promoção: preservar o produto comercial

**O usuário determinou preservar integralmente a estrutura UX/UI, design, layout e navegação do original. Esta interface STAGING não é proposta de redesign do produto. Não copiar seus templates, menus, CSS, factories ou snapshot ao original.** O backend homologado deverá ser integrado aos controles/telas comerciais existentes, sem substituir a estrutura visual.

Inspeção somente leitura confirmou que o original tem controle de IA próprio, mas `automation_service.py` ainda bloqueia a execução real no Supabase e declara `requires_migration`. Portanto, o botão STAGING aprovado não homologa automaticamente o backend antigo do original. Próxima etapa concreta: adaptar e testar esse contrato existente em cópia, mantendo os templates originais, e preparar migrations seletivas. A pasta original permanece intocada.

Hashes observados para rastreabilidade do original: app/main.py BB018B092B8D821C138040EEC1022FAF827599EEAF1067D281D7A8B7F5C66767; app/templates/base.html 9742555C07384A7040DB5CCD3981A474C141228515F694BAAB4AAA57C73680EB. Perfil `.env.h1_005b2` preservado:46385242d3937fc202c6d3a0e33f4ccc7d0a0de0a8684eae20311c3cbcdfbb2c.

## Railway: conta preparada, aplicação não publicada

Usuário autorizou cadastro/login Railway; concluiu a verificação humana e aceite dos termos no navegador. Conta autenticada, Limited Trial de 30 dias/US$ 5. Foi criado um projeto vazio, inicialmente rotulado homologação; após esclarecimento do usuário, foi renomeado VENDRA e seu único ambiente vazio renomeado production, reservado exclusivamente para o original após homologação.

**Não há serviço, deploy, banco, credenciais da aplicação, domínio comprado ou aplicação online no Railway.** O usuário determinou manter STAGING local e criar um ambiente online de teste somente se indispensável para algum teste concreto. Não publicar STAGING por conveniência nem tratar a conta/projeto vazio como hospedagem funcional.

- [Projeto VENDRA reservado no Railway](https://railway.com/project/caad2a82-373d-441c-8403-f3a7903a264f?environmentId=d4a67a07-5075-4b3a-82bd-338d50126d3f)
- [Conversas no STAGING local](http://127.0.0.1:8011/conversas)
- [Evidências da integração real anterior](VALIDACAO_INTEGRADA_H1_006I.md)

## Comandos e próximos blocos

Código já aplicado na cópia Windows, sem reinstalação manual nesta sessão. Servidor 8011 reiniciado com o mesmo perfil privado explícito, transporte/worker desligados; demais instâncias preservadas.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.dispatch_portal_start --config .env.h1_005b2 --check
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

O primeiro comando somente confere o perfil; o segundo executa regressão em cópia limpa. Não iniciar outro servidor sobre 8011 enquanto estiver em uso. Instalador da entrega faz dry-run por padrão, backup/reversão dos arquivos modificados ao aplicar; não executa SQL, Make, worker ou hospedagem. Esta entrega é somente STAGING, proibida como pacote visual de promoção.

Próximos blocos combinados: adaptar backend ao contrato e às telas originais em cópia; reconciliar migrations/configurações próprias; ensaiar backup/restauração e rollback. Só depois promoção seletiva do original preservando design e publicação Railway, seguida dos testes HTTPS/callbacks/persistência no servidor. Limpar contas CODEX somente ao concluir a homologação total.

