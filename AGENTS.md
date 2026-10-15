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

- Autorizacao permanente de 14/10/2026: documentar comandos e executa-los autonomamente quando necessarios no escopo autorizado, sem depender de execucao manual pelo usuario. Registrar acao, destino, revisao, validacao e resultado. Ver docs/COMANDOS_OPERACAO.md.

- Regra explicita de 14/10/2026: tuneis/cenarios do original pertencem a ambiente testado; para STAGING copiar e trabalhar isoladamente, nunca substituir/redirecionar o original. Copia sob demanda Make 6639761 sem webhook Meta e com envio bloqueado; nao reverter historico autorizado automaticamente.

## Continuidade H1-006I (15/10/2026)
Ler docs/VALIDACAO_INTEGRADA_H1_006I.md e ultimo checkpoint docs/VALIDACAO_ATUAL.md. SQL09 e Make Inicial autorizados/aplicados; formulario real ate read automatico aprovado. Seis callbacks IA REV9 originais autorizados/aplicados, resposta operacional unica read automatico; duas reservas bloqueadas canceladas. Handoff backend e oito respostas tardias suprimidas. 33 verificacoes funcionais portal/CRM/permissoes/reinicio aprovadas; fixtures e sessoes proprias limpas. Transporte/filtros/worker desligados e flags removidas. Aplicacao e44d0bb inalterada/218testes anteriores; nao repetir sem mudanca. Proximo: UI operacional WhatsApp e controle humano/IA (portal STAGING atual tem apenas atendimento interno), composicao seletiva producao/migrations, backup/restauracao banco e hosting/HTTPS. Sem promocao principal; nao limpar contasCODEX antes do fim. Fonte/documento em consolidacao H1-006I, Mestre v1.45 previsto; conferir final do checkpoint para hashes/links efetivamente publicados.
