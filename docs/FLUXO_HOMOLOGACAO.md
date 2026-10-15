# Desenvolvimento, acompanhamento Windows e promoção

O usuário definiu este fluxo em 14/10/2026: acompanhar cada entrega na pasta Windows de testes e atualizar o principal apenas quando o conjunto estiver correto e homologado.

## Destinos

- Nuvem: checkout de desenvolvimento `/workspace/Projetos`.
- Windows de testes: `C:\Users\israe\Downloads\Automações\VENDRA_v0.0.4_Windows_Source\VENDRA_v0.0.4_Windows - Copia\vendra_starter`.
- Principal: deve ser identificado antes da primeira promoção. O arquivo do Drive contém a pasta irmã `VENDRA_v0.0.4_Windows\vendra_starter`, mas isso não comprova qual instalação está efetivamente em uso no computador do usuário.

Não há acesso direto ao disco C: nesta sessão. O acompanhamento é viabilizado por pacotes de atualização que o usuário aplica localmente. Não há sincronização automática em segundo plano. Um acesso remoto ou agente local precisaria ser disponibilizado para aplicação direta; não foi instalado nem configurado.

O usuário autorizou publicar o pacote em uma branch de entregas no GitHub e pediu links em todas as entregas futuras. O pacote inicial está na branch `entregas/staging-20261014` de `geanprofcd/Projetos`, com download e instruções verificados. Não repetir links de artefatos desta interface como única entrega: o download falhou para o usuário.

- Download: https://github.com/geanprofcd/Projetos/raw/refs/heads/entregas/staging-20261014/entregas/VENDRA_STAGING_ACOMPANHAMENTO_20261014.zip
- Página do arquivo: https://github.com/geanprofcd/Projetos/blob/entregas/staging-20261014/entregas/VENDRA_STAGING_ACOMPANHAMENTO_20261014.zip
- Instruções: https://github.com/geanprofcd/Projetos/blob/entregas/staging-20261014/entregas/README.md

## Entrega de teste

Cada alteração deve registrar origem/versão, arquivos afetados, testes executados e limites. Entregar um ZIP com hashes e instruções para a pasta de testes; preservar configurações e estado. Fazer backup dos arquivos diferentes antes de substituí-los. Não colocar chaves, credenciais, dados do banco ou blueprints com headers secretos no pacote.

O pacote inicial desta rotina contém o snapshot de código e documentação preparado nesta máquina, incluindo o módulo original recuperado. Ele não é uma promoção ao principal e não aplica SQL. O instalador Windows limita o destino à cópia de testes e não toca a pasta principal. A primeira aplicação permite alinhar a cópia ao snapshot local; entregas seguintes devem preferir somente os arquivos alterados.

## Homologação e promoção

1. Executar testes pertinentes ao conjunto alterado e corrigir falhas explicadas pela configuração.
2. Validar o fluxo funcional correspondente no STAGING. Para banco, avaliar persistência, permissões, concorrência e idempotência quando afetadas; mocks não substituem esses resultados.
3. Validar a execução Windows quando a alteração depender dela, registrando o resultado real ou a evidência enviada pelo usuário.
4. Registrar o conjunto aprovado e pendências. Falhas de aplicação ainda não resolvidas impedem promoção desse conjunto.
5. Após homologação, aplicar somente os arquivos e mudanças de banco aprovados ao principal, com backup, configurações próprias e verificação do fluxo. A autorização condicional já existe; não solicitar uma segunda autorização genérica para a mesma promoção.

Não promover dados de teste, tabelas `staging_*`, `.env`, sessões ou credenciais. A promoção não habilita transporte real como efeito colateral. Testes de envio e mudanças externas precisam estar no escopo concreto do trabalho autorizado.

Se não houver acesso real ao destino, entregar o pacote de promoção e registrar aplicação como pendente. Nunca registrar uma atualização Windows ou principal como executada apenas porque o ZIP foi gerado.
