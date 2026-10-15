# Validação inicial — 14/10/2026

Diretório de trabalho: `/workspace/Projetos`. Python 3.12.14; ambiente virtual `/workspace/vendra-runtime/.venv`.

| Verificação | Resultado |
| --- | --- |
| Git remoto | Leitura autenticada funcionou; nenhum HEAD ou branch remoto retornado na inspeção inicial |
| Anexos ZIP | 19 arquivos, 14 conteúdos distintos, 5 duplicatas idênticas |
| Integridade | Manifestos e listas SHA-256 fornecidos verificados sem divergência |
| Importação | 234 arquivos da sequência base → B8 → B9 → hotfixes, com conteúdo preservado |
| Instalação Python | `pip install -r requirements.txt` concluiu com código 0 |
| Dependências | `pip check`: nenhuma dependência quebrada |
| Suíte completa | Código de saída 1; 103 testes aprovados, 5 falhas de carregamento de módulo |
| Smoke isolado existente | Código de saída 0; 7 verificações aprovadas usando stubs/mocks previstos no próprio script |
| Inicialização Uvicorn | Código de saída 1; módulo local de credenciais ausente |
| Supabase real | Não executado: projeto e credenciais ainda não configurados |
| Make/Meta reais | Não executado: cenários analisados estaticamente; nenhuma mensagem enviada |
| Google Drive | Tentativa de leitura bloqueada pelo proxy: HTTP 403 |

O unittest informa `Ran 108 tests`, mas cinco são placeholders de importação `unittest.loader._FailedTest`, não testes de aplicação executados. Os 103 testes restantes terminaram aprovados. Os módulos B2, B3, B4, B5 e B6 não carregaram devido a `app.services.local_credentials_service` ausente. Não houve testes pulados declarados pelo runner.

Suites carregadas: B1, B7, B8, B9, flash/F5, conflito de versão, PT409 e PT409 legado. Várias usam mocks; seus resultados não validam concorrência PostgreSQL, permissões RLS reais ou transporte WhatsApp.

Logs da execução atual ficam fora do repositório em `/workspace/vendra-analysis`: `install.log`, `tests.log`, `startup.log`. A lista local de versões instaladas está em `/workspace/vendra-runtime/resolved-requirements.txt`; não é lockfile do produto.

Estado: análise e instalação preparadas; aplicação e ambiente integrado ainda não prontos. O rascunho de configuração não constitui publicação nem comprova restauração em outra tarefa.
