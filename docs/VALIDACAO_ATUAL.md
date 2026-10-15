# Estado atual — 14/10/2026

Atualização Windows: o usuário aplicou o pacote e executou os 157 testes. O log comprova 156 aprovações e um erro de codificação CP1252 no teste de template B1. Corrigido o instalador para usar Python `-X utf8`; aguardar nova execução e homologação funcional. Ver `VALIDACAO_WINDOWS_UTF8.md`.

## Chave backend retestada

Após nova publicação/configuração, o binding `SUPABASE_SERVICE_ROLE_KEY` passou na leitura pelo SDK oficial. A URL e o Reference ID conferem com o projeto `ljufhqnadzltqbtdaulv`. Nenhuma chave ou registro pessoal foi impresso.

| Objeto consultado | Resultado / quantidade |
| --- | --- |
| profiles | SDK OK / 1 |
| customers | SDK OK / 1 |
| tickets | SDK OK / 2 |
| opportunities | SDK OK / 1 |
| staging_transport_contracts | SDK OK / 3 |
| whatsapp_outbox | SDK OK / 0 |
| dispatches | SDK OK / 0 |
| messages | SDK OK / 0 |

As consultas adicionais usaram HEAD com contagem exata, sem baixar conteúdo dos registros. Nenhum dado remoto foi alterado, nenhum SQL foi aplicado e nenhuma mensagem foi enviada.

## Desenvolvimento e execução

- O módulo original de credenciais já está recuperado; a suíte local mais recente passou em 157 testes com FastAPI 0.115.14.
- O demo local já foi iniciado e validado por HTTP, incluindo login e páginas de CRM. Isso comprova desenvolvimento local, não homologação de todos os fluxos no Supabase real.
- O guard de STAGING ainda rejeita os prefixes das chaves proxy injetadas no runtime, embora o SDK consiga usá-las nas requisições HTTPS ao destino configurado. Seu teste em ambiente preparado retornou dois erros de formato: anon/publishable e secret/service_role. Portanto, o entrypoint de STAGING real na nuvem ainda exige um ajuste de compatibilidade em tarefa de código; não remover o guard nem substituir valores por credenciais fictícias para fazê-lo passar. Esse problema de formato não prova que as chaves reais sejam inválidas.
- O Make ainda não foi conectado ou acionado.

## Acompanhamento Windows

O disco C: não está montado e não há ferramenta de acesso remoto ao computador do usuário. Foi registrada a pasta exata de testes e a regra de promoção condicional em `AGENTS.md` e `FLUXO_HOMOLOGACAO.md`.

Pacote preparado: `/workspace/vendra-deliveries/VENDRA_STAGING_ACOMPANHAMENTO_20261014.zip`. A integridade ZIP/CRC e os hashes dos arquivos foram verificados; os mesmos fontes do pacote passaram em 157 testes, com o comando de módulos usado pelo instalador. O script PowerShell não foi executado nesta máquina: Windows/PowerShell não está disponível. Ele inclui conferência sem escrita, aplicação na cópia de testes, backup dos arquivos diferentes, preservação de configurações/dados e execução dos testes numa cópia idêntica sem `.venv` sob a raiz. Falhas impedem homologação/promoção e conservam o registro de backup. Não aplica SQL nem aciona cenários Make.

Aplicação no Windows e homologação do conjunto nesse destino ainda não executadas nesta sessão.

O principal permanece sem atualização por esta sessão: o conjunto STAGING não tem homologação funcional completa registrada para promoção. O pacote de acompanhamento é somente para a cópia de testes.
