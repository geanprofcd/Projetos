# Validação após publicação — 14/10/2026

Este registro preserva o primeiro teste após publicação. A chave backend foi corrigida e retestada com sucesso depois; consulte `VALIDACAO_ATUAL.md` para os resultados atuais.

## Resultado atual

O desenvolvimento local está desbloqueado. A integração com dados reais ainda depende de corrigir o binding backend do Supabase.

- A configuração publicada foi lida sem rascunho pendente; os bindings de URL, Reference ID e duas chaves Supabase estavam presentes no runtime.
- O hostname e Reference ID do runtime correspondem ao projeto `ljufhqnadzltqbtdaulv`.
- `/auth/v1/health` e `/auth/v1/settings`, usando a chave pública, responderam HTTP 200.
- O SDK administrativo e requisições REST de leitura com a chave backend retornaram HTTP 401. O REST informou `Invalid API key`, tanto com header apikey apenas quanto com apikey e Authorization. Nenhum valor de chave foi impresso.
- O link Google Drive passou a funcionar após publicação. O arquivo `VENDRA_v0.0.7z` foi baixado; apenas quatro arquivos de código/metadados foram extraídos para inspeção, sem copiar configurações, bancos, ambientes virtuais ou programas do pacote.
- O módulo original `app/services/local_credentials_service.py` foi recuperado da cópia Windows. `auth_service.py`, `config.py` e `version.json` do mesmo diretório são idênticos aos arquivos já importados. Somente o módulo ausente foi acrescentado ao checkout; sua origem e hash estão em `IMPORTACAO.json`.
- A instalação inicial havia resolvido FastAPI 0.143.0 / Starlette 1.8.0, que mudam a representação das rotas e quebram o teste de isolamento B2. Foi instalada FastAPI 0.115.14, dentro da faixa declarada pelo projeto, com constraint externa ao checkout. Nenhum teste ou declaração de dependências do produto foi alterado.
- Com a versão compatível, **157 testes foram executados e aprovados**, sem falhas, erros ou skips. `pip check` aprovado.

## Aplicação local

O helper `/workspace/vendra-runtime/start_demo.py` inicia a aplicação original em demonstração local, com estado independente em `/workspace/vendra-runtime/demo`, segredo de sessão gerado por processo e credenciais externas removidas somente do ambiente desse processo. Ele não altera os bindings da máquina.

Startup real do Uvicorn aprovado. As requisições locais verificaram:

| Verificação | Resultado |
| --- | --- |
| `/health` | HTTP 200; demo ativo, Supabase configurado false, WhatsApp desabilitado |
| GET `/login` | HTTP 200 |
| POST `/login` | HTTP 303 e cookie de sessão, sem imprimir credenciais |
| `/clientes` | HTTP 200 com sessão autenticada |
| `/atendimentos` | HTTP 200 com sessão autenticada |
| `/oportunidades` | HTTP 200 com sessão autenticada |
| `/configuracoes/funis` | HTTP 200 com sessão autenticada |
| `/produtos` | HTTP 200 com sessão autenticada |

Comando de startup, usando o checkout existente e sem worktree:

```bash
cd /workspace/Projetos
/workspace/vendra-runtime/.venv/bin/python /workspace/vendra-runtime/start_demo.py
```

Esse processo não comprova login real no Supabase nem envio pelo Make. A aplicação H1-005B9 de STAGING continua exigindo configuração própria e projeto real; Make ainda não foi conectado. Não houve alteração remota de dados, execução SQL ou mensagem enviada.

O módulo recuperado, o helper e a constraint foram acrescentados depois da publicação informada pelo usuário. Sua persistência em uma futura máquina depende de uma nova publicação do snapshot; a validação desta máquina não comprova restauração futura.

## Próximo ajuste externo

Revisar somente o binding seguro `SUPABASE_SERVICE_ROLE_KEY` nas configurações do ambiente, usando a chave backend do próprio VENDRA-STAGING: legacy service_role ou a Secret key apropriada. Não criar requisito duplicado nem enviar valores no chat. Depois de salvar e propagar a correção, repetir uma leitura limitada pelo SDK. A mensagem de erro confirma rejeição da chave enviada; não permite concluir a causa exata (valor incorreto, chave de outro projeto, revogação ou propagação do binding).
