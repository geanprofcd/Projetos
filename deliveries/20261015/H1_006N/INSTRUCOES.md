# H1-006M/N - Composer, anexos e histórico comercial no STAGING

Já aplicado na cópia Windows. 263 testes Windows, 22 verificações funcionais reais do composer/anexos e oito do histórico aprovados. SQL11 anterior continua aplicado somente no STAGING; nenhum SQL adicional nesta rodada. Bucket privado ticket-attachments criado no STAGING, sem acesso público. Nenhum WhatsApp transmitido, worker/lote habilitado ou arquivo promovido ao original.

Design comercial preservado. A única mudança de HTML é input CSRF oculto no composer; nenhum CSS/JS/layout/navegação modificado. Pacote cumulativo de19arquivos, incluindo dependências K/L, testes, documentação e SQLs separados. Não contém credenciais, dados, objetos Storage, sessões ou perfis privados. Não instala no original, executa SQL/Make, provisiona Storage, inicia serviços ou habilita a flag persistente.

Fonte: https://github.com/geanprofcd/Projetos/commit/85c76ba5b389ceecf401d29efcc51be4749a62ce
Composer: https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_COMPOSER_ANEXOS_H1_006M.md
Histórico: https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_HISTORICO_COMERCIAL_H1_006N.md
Prévia local: http://127.0.0.1:8014/atendimentos

Não é necessário instalar novamente nesta sessão. Em outra cópia STAGING preparada:

```powershell
Get-FileHash -LiteralPath '.\VENDRA_H1_006N_COMPOSER_HISTORICO_STAGING_20261015.zip' -Algorithm SHA256
Expand-Archive -LiteralPath '.\VENDRA_H1_006N_COMPOSER_HISTORICO_STAGING_20261015.zip' -DestinationPath '.\H1_006N_CONFERENCIA'
powershell -NoProfile -ExecutionPolicy Bypass -File '.\H1_006N_CONFERENCIA\tools\aplicar_callbacks_staging.ps1' -Destino 'CAMINHO_DA_COPIA_STAGING'
```

Último comando somente confere. -Aplicar copia arquivos diferentes com backup e rollback.json. Preserva .env, runtime, .vendra-data e venv. SQL11/12 são arquivos separados; não executados pelo instalador. Reversão de arquivos não reverte SQL/Storage. Bucket privado precisa ser provisionado separadamente no ambiente correspondente, sem copiar objetos de teste.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.commercial_preview_start --config .env.h1_005b2 --check
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

Primeiro confere perfil, segundo executa regressão. Não iniciar segunda instância na8014. Perfil privado desta sessão tem controle persistente true/transporte false; padrão fontefalse. STAGING online somente se indispensável. Principal/Railway sem promoção/deploy.

Limites: envio humano/mídia ao provedor, idempotência de duplo clique, recuperação de escrita, novos atendimentos IA, criação/importação/lote comerciais, backup/restauração e hospedagem ainda pendentes. Próximo: contrato de reserva/vínculo da outbox humana, não ativar cegamente o REV2 antigo.

# H1-006M - Composer humano e anexos no STAGING

Validação em 15/10/2026, na cópia Windows local8014 e no Supabase VENDRA-STAGING. Original, seu banco e design preservados; sem hospedagem ou envio WhatsApp nesta rodada.

## Correções aplicadas na cópia

O formulário comercial agora inclui um token CSRF invisível, validado antes de leitura/escrita. A comparação com o template original confirmou que essa linha é a única diferença do HTML: nenhum layout, elemento visível, CSS, JS ou navegação foi alterado. A pasta original não recebeu arquivos.

Resposta humana WhatsApp passa a exigir confirmação do handoff antes de gravar mensagem, anexo ou outbox. Antes, a falha do controle era ignorada e o fluxo continuava; agora retorna422 e preserva o texto digitado. A camada persistente sob flag registra corretamente canal WhatsApp e autoria humana; notas internas continuam internas.

O STAGING não tinha bucket de anexos. Foi criado `ticket-attachments`, privado, limite50MiB, exclusivamente nesse projeto, sem conceder acesso público ou alterar RLS. O limite de cada tipo de arquivo continua validado também pelo backend. O original não foi provisionado nesta etapa.

## Evidências aprovadas

- **258 testes Windows passaram em2,949s**, em snapshot limpo/UTF8: `VENDRA-validacoes/staging_20261015_230826_625_cf7397d5/resultado.json`. Nove novos casos exercitam CSRF, handoff antes da persistência, falha fechada, arquivo inválido, limite de seis anexos, janela expirada, nota interna, metadados humanos e rollback técnico em falha simulada do segundo upload. O traceback `storage unavailable` no log é esperado desse teste de falha; suíte terminou OK/código0.
- **22 verificações funcionais reais HTTP/SDK/banco/Storage** na rodada concluída: login Comercial; campo CSRF invisível; CSRF ausente/incorreto sem escrita; mensagem vazia; executável; sete anexos; texto/anexo persistidos; handoff com ator Comercial; canal/autoria humanos; uma outbox pending sem WAMID; checksum/tamanho do anexo; escape do texto; download autorizado por URL assinada; bytes reais iguais; acesso público ao bucket negado; download anônimo redirecionado ao login; anexo em outro atendimento404; nota interna sem nova outbox; janela expirada422 sem escrita; atendimento encerrado/handoff recusado422 sem escrita; ausência de envio real.
- Foi usada uma entrada **sintética**, identificada como fixture, para abrir a janela do atendimento de teste. Não é evidência de recepção real do Meta. Recepção e IA reais anteriores permanecem documentadas em H1-006I.
- Duas tentativas anteriores não foram contadas como homologação completa: source `internal` inválido da fixture foi corrigido para `portal`; depois, um GET da tela falhou por ReadError WinError10035 do Supabase. Ambas tiveram limpeza automática. Rodada final manteve todas as assertions e aprovou os22casos. O auxiliar permite no máximo uma releitura de GET em5xx, registra a ocorrência e nunca repete POST/envio; não altera as verificações. Verificar logs de conectividade caso reapareça.
- Fixtures próprias: dois atendimentos, mensagens sintéticas, anexo e objeto Storage, outbox pendente e sessões criadas pela rodada foram removidos. Exclusão restrita a IDs/títulos/prefixos registrados pelo próprio teste. Evidências reais de WhatsApp, cliente existente e contas CODEX preservados. Bucket privado permanece como configuração funcional do STAGING.

O navegador passou a apresentar timeouts de conexão CDP após o clique H1-006L. A rodada M foi validada por endpoints comerciais reais, HTML e bytes de Storage, sem alegar clique ou screenshot novo no navegador. A comparação do template, descontando apenas o input oculto, confirmou layout inalterado. Não confundir isso com uma nova homologação visual de todos os estados interativos.

## Limites e próximos blocos

Esta rodada homologa persistência e anexos privados no STAGING, com saída enfileirada e não transmitida. **Não homologa envio humano até o WhatsApp, envio de mídia ao provedor, idempotência de duplo clique do composer nem recuperação completa após falha de rede de uma escrita.** O handoff ocorre antes da gravação, mas a sequência mensagem/anexo/outbox ainda não é uma única transação de banco. A reversão técnica foi exercitada com falha simulada; não declarar atomicidade total.

Continuar o levantamento do fluxo humano no Make e a integração comercial de Disparos/importação/lote, além do padrão IA de novos atendimentos. Não habilitar worker/lote/envio como efeito de instalar código. Depois ensaiar backup/restauração e promoção seletiva, preservando design, estado e configurações do original. Só então publicar o original finalizado e validar callbacks/HTTPS/reinício no servidor. STAGING online somente se indispensável.

## Comandos

Código já aplicado na cópia local, prévia8014 reiniciada. Não é necessária reinstalação nesta sessão.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.commercial_preview_start --config .env.h1_005b2 --check
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

Primeiro apenas confere perfil. Prévia ativa usa perfil privado explícito com controle persistente true e transporte false; perfil base preservado. Não duplicar processo na8014. Nenhum SQL adicional foi aplicado na rodada M. Provisionar Storage no original será uma etapa separada, após reconciliação da configuração já existente, sem copiar objetos de teste.

[Controle da equipe e configuração global](VALIDACAO_EQUIPE_GLOBAL_H1_006L.md) | [Estado atual](VALIDACAO_ATUAL.md)


# H1-006N - Histórico comercial de Disparos e levantamento da saída humana

15/10/2026, somente cópia Windows/STAGING local8014. Original, banco principal, layout comercial e Make preservados nesta rodada.

## Aplicado e validado

Sob a flag persistente já existente, `dispatch_service.list_dispatches/get_dispatch` passam a consultar os registros reais do Supabase, com limite e campos explícitos. Antes, o caminho real retornava lista vazia/None, ocultando os disparos já homologados. Os componentes comerciais de histórico/status existentes agora recebem esses dados, inclusive Lido. Campos de resposta bruta do Make não são selecionados.

Criação/importação/lote comerciais não foram habilitados. O reenvio real ganhou bloqueio explícito antes de qualquer transporte ou consulta: permitir leitura não pode ativar o caminho demo de reenvio por acidente. Flag desligada conserva o comportamento anterior; não houve alteração de template ou CSS de Disparos.

- **263 testes Windows passaram em2,829s**, snapshot limpo/UTF8, incluindo cinco novos de leitura limitada, campos, UUID inválido, flag desligada e reenvio sem transporte. Relatório privado `VENDRA-validacoes/staging_20261015_232026_179_d9cee42b/resultado.json`.
- **Oito verificações funcionais HTTP/SDK reais**: login Comercial; histórico lê registros existentes; Lido real aparece; reenvio permanece422 explicativo; criação sem canal habilitado422; CSRF inválido403; Comum bloqueado em histórico/reenvio; nenhum disparo foi alterado. Sessões próprias revogadas. Nenhum envio, SQL, worker, migration, fixture de disparo ou mudança Make nesta rodada.

## Levantamento Make somente leitura

Inventário completo para nomes contendo VENDRA na equipe292724 retornou sete cenários, dois ativos: REV9 recepção/IA6534261 e Disparo Inicial6561096. Os demais correspondem a cópias/base/testes inativos. Não é uma afirmação de que toda a conta, incluindo outros nomes, não tenha automações.

O cenário `VENDRA - Meta -> VENDRA -> IA -> VENDRA Outbox (REV2 v0.0.13)`6516018 está inativo. Inspeção estrutural confirmou trigger de recepção Meta, passagem pela IA e envio direto WhatsApp; não é evidência de um worker que reserve/processa respostas humanas pendentes do composer. Conexão WhatsApp é a antiga10964730, portanto não ativar ou reutilizar cegamente como saída Israel.

[REV2 inspecionado](https://us2.make.com/292724/scenarios/6516018/edit) | [REV9 atual](https://us2.make.com/292724/scenarios/6534261/edit) | [Disparo Inicial](https://us2.make.com/292724/scenarios/6561096/edit)

Próximo bloco concreto: localizar/reconciliar o contrato de saída humana existente, preparar reserva/vínculo e idempotência, então validar um worker isolado de teste limitado ao número autorizado. Não ativar automaticamente REV2, lote, polling amplo ou envio por efeito desta leitura. A persistência/anexos M não equivale à transmissão ao provedor.

Continuam pendentes padrão IA em novos atendimentos, criação/importação/lote na tela comercial, idempotência e recuperação do composer, backup/restauração, promoção seletiva e hospedagem do original finalizado. STAGING online somente se indispensável; design original deve permanecer preservado.

## Comandos

Já aplicado na cópia e carregado na prévia8014; nenhuma reinstalação necessária. Para conferir perfil e regressão:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.commercial_preview_start --config .env.h1_005b2 --check
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

Não iniciar segunda instância sobre8014. Perfil privado de teste fora do Git; transporte false. Fonte e pacote M/N não promovem arquivos ao principal nem executam SQL/Make.

[Composer e anexos](VALIDACAO_COMPOSER_ANEXOS_H1_006M.md) | [Controle da equipe](VALIDACAO_EQUIPE_GLOBAL_H1_006L.md)
