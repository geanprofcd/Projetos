# Recuperação isolada — avanço após v1.62

Nenhum serviço de produção alterado nesta etapa. SQL34/paginação e recepção de
mídias permanecem na publicação original anterior.

## Implementado e conferido

- `tools/recovery_bundle.py`: pacote AES-256-GCM, chave separada, manifesto de
  hashes, rejeição de adulteração/caminhos inseguros e destino já existente.
  Não acessa rede/banco, não busca credenciais ou copia `.env` automaticamente.
- `tools/recovery_postgres_local.cjs`: ensaio sem URL de banco remoto, runtime
  PGlite0.5.10 privado fora do aplicativo; nenhuma dependência nova na produção.
- Estrutura atual de26 tabelas,262 colunas,153 constraints e51 índices lida por
  metadados do catálogo original, sem linhas de clientes/mensagens.
- Nove registros sintéticos: perfil/cliente/funil/etapa/ticket/card/mensagem/
  anexo/outbox cancelada, em PostgreSQL local em memória. Nenhuma conta online.
- Sete checks: criação de tabelas, relacionamentos/índices, dump/reabertura e
  hashes de todas as tabelas, vínculos chat/card/anexo, UTF8/aspas, rejeição de
  WAMID duplicado e FK para cliente inexistente.
- Pacote sintético cifrado com5 arquivos/4.728.480bytes; restauração em nova pasta
  e mais dois checks: dump decifrado reaberto/hashes iguais e arquivo conferido
  contra tamanho/checksum do banco. Cinco testes Windows da proteção passaram.

O primeiro ensaio local encontrou uma suposição errada da ferramenta: tabelas de
configuração usam chave própria em vez de `id`. Comparação corrigida para conteúdo
canônico; rodada final aprovada. Não confundir essa falha com erro no VENDRA.

## Estado histórico antes da autorização real (encerrado no adendo abaixo)

Não há backup de registros reais de produção nesta etapa. A revisão automática
rejeitou essa exportação antes de devolver dados, por falta de autorização
específica para payload sensível e destino. Alternativa segura executada: somente
metadados de estrutura e dados gerados localmente. Plano exato preparado em
[PLANO_BACKUP_PRIVADO_ORIGINAL.md](PLANO_BACKUP_PRIVADO_ORIGINAL.md).

Auth apenas simulado por UUID para validar FK; sem login real restaurado. Não
foram restaurados funções/triggers operacionais, RLS de API, Storage gerenciado,
serviço Supabase ou ambiente Railway. Um dump PGlite é próprio desse runtime;
não é substituto de pg_dump/restore completo do projeto Supabase.

## Comandos usados no ensaio

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_recovery_bundle
python -X utf8 -m tools.recovery_bundle seal --source "PASTA_PRIVADA_REVISADA" --archive "PASTA_BACKUPS/snapshot.vrb" --key "PASTA_CHAVES/key.bin"
python -X utf8 -m tools.recovery_bundle restore --archive "PASTA_BACKUPS/snapshot.vrb" --key "PASTA_CHAVES/key.bin" --destination "PASTA_NOVA_ISOLADA"
```

Comandos de referência, já conferidos com dados sintéticos. Não usar a ferramenta
para coletar dados reais antes da autorização pendente. Não compartilhar a chave
ou incluir backup/dados no pacote público.

## Backup privado autorizado e executado — 19/10/2026 — v1.63

A pendência de autorização está encerrada para o plano descrito: usuário aprovou
explicitamente conteúdo sensível, destino cifrado local e ensaio isolado. Após
isso, exportação única/consistente de24tabelas/452registros, sem app_sessions,
user_invitations ou credenciais/tokens Auth. Captura2026-10-20T00:24:08.150652Z
(19/10 às21:24 Brasília). Dois anexos privados/23.506.730bytes baixados e
conferidos contra tamanho/SHA256 do banco. Origem somente leitura.

Estrutura26tabelas/262colunas/153constraints/51indices reconstruída no PostgreSQL
local;452registros carregados, dump reaberto e hashes/contagens iguais. Sessões e
convites vazios. Banco e arquivos cifrados em8arquivos de pacote AES-256-GCM,
28.289.640bytes; chave aleatória32bytes em pasta privada separada, não publicada.
Pacote decifrado em pasta nova, dump reaberto novamente, hashes de26tabelas e
ambos os anexos conferidos. Sete checks reais aprovados, sem worker/callback ou
conexão a clientes. Cópias temporárias em claro removidas após conferência.

Arquivo privado: recovery-original-20261019/snapshot.vrb sob a pasta privada do
Codex descrita no plano. SHA256c089915fcbcedb174c4ff2a039a01568126720ff2ac00a64ea31e754aebf0e50.
Somente resultado sanitizado, ferramentas e documentação podem ir ao Git/pacote.
Backup e chave NÃO fazem parte da entrega pública.

Primeiro download encontrou limite de caminho Windows; layout corrigido para
objetos porSHA256 e storage-map.json privado, preservando o nome/caminho original
na captura. A primeira tentativa não completou o backup de arquivos; a rodada
final acima completou. Um teste no sandbox falhou por permissões no Temp Windows;
repetição autorizada fora do sandbox:5testes passaram em0,077s.

Continua fora do escopo comprovado: login/Auth, funções/triggers operacionais,
políticas daAPI, Storage gerenciado, serviços Railway/Make e recuperação de
projeto Supabase completo. O Auth local é apenas UUID paraFK, sem senha. Arquivo
e chave continuam no mesmo computador em pastas separadas; uma cópia fora dele
com custódia segura da chave depende de destino/decisão específica. Nenhum
serviço pago, armazenamento externo ou recorrência foi criado.

## Cópia externa do backup concluída —20/10/2026

Pasta indicada pelo usuário: PROJETO - VENDRA, id18J1yxZK2WKTCl11_xqs7bWFrP__z4h8e.
Primeiro upload recusado pelo Google com403/insufficientParentPermissions.
Conta conectada contato@i9se.digital; após o usuário ajustar o acesso, upload
concluído. Arquivo1TdOFGpUtgIyJVbByWwmorPGXRUBTGufS, VENDRA_Backup_Cifrado_20261019.vrb,
28.289.640bytes. Metadados lidos e download autenticado completo conferido contra
SHA256c089915fcbcedb174c4ff2a039a01568126720ff2ac00a64ea31e754aebf0e50.
URL:https://drive.google.com/file/d/1TdOFGpUtgIyJVbByWwmorPGXRUBTGufS/view
Somente cifrado foi enviado; chave NÃO enviada e permanece em pasta privada
separada noPC. Falta custódia independente da chave para sobreviver à perda do
computador. Nenhuma recorrência criada nem estado de compartilhamento alterado
pela automação. Não publicar a chave junto do arquivo.
