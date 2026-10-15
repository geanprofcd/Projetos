# VENDRA: continuidade por Git

Leia docs/VALIDACAO_GIT_STAGING.md para o checkpoint vigente. docs/VALIDACAO_ATUAL.md e outros documentos historicos do payload registram sessoes anteriores e nao comprovam o estado atual.

- Documento Mestre e a referencia de requisitos/decisoes; Git registra codigo e evidencias.
- Desenvolver e validar STAGING antes de promover seletivamente ao principal. Publicar codigo/pacotes nao equivale a homologar ou instalar.
- Preservar .env, .env.h1_005b2, runtime, .vendra-data, sessoes e venv; nao publicar segredos/dados locais.
- SQL, Make, worker e envio sao operacoes separadas. Nao habilitar IA como efeito de instalar codigo.
- Windows: usar Python -X utf8 em testes e startup. Nao mudar assertions para contornar encoding.
- Atualizar Documento Mestre cumulativo nas pastas autorizadas, com links/comandos, evidencias e limites. Nao pausar a cada atualizacao documental.
- Registrar commit aplicado, destino e validacao. Promover somente conjunto homologado com backup, sem mover configuracoes/dados STAGING ao principal.
- Contas CODEX permanecem ate homologacao total; limpar apenas contas de teste identificadas no ledger autorizado.
- Nao criar worktree sem necessidade/autorizacao aplicavel. Este checkout e separado do runtime Windows.
