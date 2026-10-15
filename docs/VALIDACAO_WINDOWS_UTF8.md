# Windows — correção de execução UTF-8 — 14/10/2026

O usuário enviou a execução real do instalador no Windows. O script validou a base, comparou os arquivos, atualizou 10 arquivos de documentação/configuração e instalou FastAPI 0.115.14 / Starlette 0.46.2. Os arquivos de aplicação já correspondiam ao pacote. `pip check` passou e a suíte executou 157 testes na cópia de verificação do backup.

Resultado informado pelo log: **156 testes aprovados, 1 erro, sem skips**. O único erro foi `tests.test_h1_005b1.PreflightTests.test_customer_template_complete`.

O traceback mostra `Path.read_text()` sem encoding explícito, usando `C:\Python314\Lib\encodings\cp1252.py`; o template UTF-8 contém byte 0x90 na posição 177, que não é decodificável em CP1252. A falha interrompeu corretamente o instalador antes de registrar homologação. Backup informado: `vendra_starter_backup_cloud_20261014_093542`, com a subpasta `verificacao` usada nos testes.

A correção está no comando do instalador: executar Python com `-X utf8` em pip e unittest. Aplicação, testes e template permanecem intactos. Não converter os fontes para CP1252, remover caracteres ou desabilitar o teste. A leitura do mesmo template em CP1252 reproduziu o erro na nuvem; o teste afetado passa com `-X utf8`. A validação do pacote corrigido na nuvem não prova execução final no Windows: aguardar a nova saída.

Entrega corrigida: `VENDRA_STAGING_ACOMPANHAMENTO_20261014_UTF8.zip`, mantendo o pacote anterior no GitHub. As instruções incluem iniciar posteriormente `python -X utf8 -m tools.staging_start` na pasta real de STAGING. O principal não foi alterado e a homologação funcional permanece pendente.
