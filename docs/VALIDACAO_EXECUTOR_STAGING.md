# H1-006G — Execução reproduzível dos testes Windows

O executor `tools/validar_staging.ps1` cria uma pasta exclusiva por execução, copia somente app/tools/tests/sql e os arquivos de referência requirements.txt, VERSION e .env.example, confere SHA-256 e executa o Python do runtime com `-X utf8`. Ignora caches, arquivos .env privados e diretórios de estado/ambientes virtuais. Não inicia aplicação, túnel, worker, Make ou migrações.

Mantém fonte copiada, manifesto, stdout/stderr e resultado.json. O tempo limite padrão é 120 segundos; ao expirar, encerra exclusivamente a árvore do processo que iniciou. Resultado diferente de zero gera falha. Não interpreta a palavra OK no log como substituto do código de saída.

## Evidência Windows em 15/10/2026

Execução da suíte: 200 testes passaram em 1,071 s, processo terminou com código zero e timed_out=false. Fonte copiada sem configuração privada; relatório e hashes preservados localmente. A primeira tentativa ficou presa no sandbox e foi encerrada sem tocar nos serviços. A execução Windows seguinte passou nos testes, mas expôs código de saída nulo no wrapper; a captura do handle foi corrigida e a execução seguinte aprovou ambos, suíte e wrapper. Fixtures independentes também comprovaram propagação de falha (código 1) e timeout (código 124, timed_out=true, limite de dez segundos). O timeout revelou ausência de log quando ambas as saídas estavam vazias; gravação explícita corrigida e retestada. Isso valida regressão offline e o executor; não amplia a homologação funcional já documentada em H1-006F.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

Opcionalmente informar `-Python 'CAMINHO_DO_PYTHON_EXISTENTE'`, `-Saida 'PASTA_DE_RELATORIOS'` e `-TimeoutSegundos 120`. A pasta de saída padrão fica no TEMP do usuário. O script não instala dependências nem apaga execuções anteriores. Seus relatórios contêm caminhos locais e ficam fora do Git público.

## Continuidade

Envio real e delivered do Disparo Inicial continuam comprovados na entrega anterior. Recepção contínua isolada na Meta e comandos reais pelo portal/CRM ainda pendem de integração e testes funcionais. A autenticação informada pelo usuário levou ao Facebook; retornar ao painel e confirmar a existência do aplicativo de teste antes de repetir criação. Não substituir callback original. Original, SQL, serviços e bloqueios de envio permanecem preservados nesta entrega.

- [Validação funcional já obtida](https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_DISPARO_INICIAL_STAGING.md)
- [Código STAGING](https://github.com/geanprofcd/Projetos/tree/desenvolvimento/vendra-staging)
