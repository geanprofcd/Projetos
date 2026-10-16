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
