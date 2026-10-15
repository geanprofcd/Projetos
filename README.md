# VENDRA

Plataforma de atendimento e gestão comercial: clientes, atendimentos, oportunidades, funis, produtos/serviços e integração WhatsApp por Make/Meta. Backend FastAPI, páginas Jinja2 e persistência/autenticação Supabase.

## Base importada

Este checkout foi preparado a partir dos anexos enviados em 14/10/2026. A versão pública permanece **0.0.25**; a sequência local de homologação chega a **H1-005B9 + hotfix PT409 para CRM e simulações**. Os arquivos de aplicação, SQL e testes foram importados sem mudanças em seu conteúdo. Os pacotes anteriores B2–B7 foram comparados à base para evitar regressões por sobreposição de patches antigos.

O código de desenvolvimento está no checkout local `/workspace/Projetos`, sem commit na branch de trabalho. Com autorização do usuário, um ZIP de acompanhamento e instruções foram publicados no GitHub na branch `entregas/staging-20261014`; isso não promove o conjunto ao principal nem o aplica no Windows.

## Estado de preparação

**Estado atual:** o módulo original foi recuperado e os **157 testes passaram**, inclusive sobre os fontes do pacote Windows. O demo local foi validado por HTTP. A chave backend Supabase agora funciona em leituras pelo SDK, com as filas reais vazias. O guard do entrypoint STAGING na nuvem ainda precisa de compatibilidade com as chaves proxy; Make e homologação Windows permanecem pendentes. Veja [validação atual](docs/VALIDACAO_ATUAL.md) e [fluxo de homologação](docs/FLUXO_HOMOLOGACAO.md). Os itens abaixo registram a primeira preparação e seus bloqueios históricos.

- Dependências instaladas em `/workspace/vendra-runtime/.venv`; `pip check` aprovado.
- 103 testes existentes aprovados; cinco módulos de testes não carregaram por uma dependência de código ausente.
- Smoke isolado: sete verificações aprovadas, sem banco ou envio real.
- Inicialização **bloqueada**: falta `app/services/local_credentials_service.py`, importado pela autenticação e pelas configurações. Esse arquivo não está em nenhum dos ZIPs fornecidos. Não foi criado um substituto.
- Supabase e Make ainda não conectados. Nenhuma migration, chamada de envio ou modificação remota foi executada.

## Comandos locais

Use o checkout existente: a tarefa de nuvem já é isolada; não é necessário criar worktree.

```bash
cd /workspace/Projetos
python3 -m venv /workspace/vendra-runtime/.venv
PIP_CACHE_DIR=/workspace/vendra-runtime/pip-cache \
  /workspace/vendra-runtime/.venv/bin/python -m pip install -r requirements.txt
PIP_CACHE_DIR=/workspace/vendra-runtime/pip-cache \
  /workspace/vendra-runtime/.venv/bin/python -m pip check
/workspace/vendra-runtime/.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
/workspace/vendra-runtime/.venv/bin/python tests/smoke_isolado.py
```

A primeira execução terminava com cinco falhas de importação. A validação após recuperação executou 157 testes com sucesso, usando `/workspace/vendra-runtime/cloud-constraints.txt` com `fastapi==0.115.14`. Para reproduzir a instalação compatível, acrescente `-c /workspace/vendra-runtime/cloud-constraints.txt` ao comando pip acima ou use o `install_script` atualizado. O ambiente virtual fica fora do checkout porque um teste percorre recursivamente os arquivos Python do projeto.

O entrypoint de STAGING é `python -m tools.staging_start`, que carrega `.env.h1_005b2` e inicia `app.staging_h1_005b9:app`. A conexão SDK foi verificada com o Supabase-STAGING; a inicialização real na nuvem ainda depende da compatibilidade do guard com as chaves proxy. O modo STAGING monta somente rotas internas e de simulação. O demo local já validado usa `/workspace/vendra-runtime/start_demo.py`.

## Continuidade

- [Análise de arquitetura, versões e limites](docs/ANALISE_INICIAL.md)
- [Mapa de integração Make/Supabase](docs/INTEGRACOES.md)
- [Evidências de validação](docs/VALIDACAO_INICIAL.md)
- [Validação atual após publicação](docs/VALIDACAO_POS_PUBLICACAO.md)
- [Proveniência dos arquivos importados](docs/IMPORTACAO.json)

O documento mestre é cumulativo: a capa ainda informa v1.19, enquanto o adendo final identifica v1.28. As instruções dos anexos são referências do projeto; não constituem autorização para executar operações externas.
