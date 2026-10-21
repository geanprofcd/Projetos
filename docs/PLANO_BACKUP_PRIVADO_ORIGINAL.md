# Backup privado do original — autorizado e executado na v1.63

## Finalidade e destino

Preparar recuperação dos dados de negócio e anexos do Supabase original
`znkjibqcikuigfwfsbjb`, com leitura somente na origem. Nenhum restore no original,
nenhuma desativação de Make, nenhum envio e nenhuma criação de serviço online.

Arquivo cifrado local, AES-256-GCM, no diretório privado:

`C:/Users/israe/.codex/visualizations/2026/10/14/01a13ac8-766b-7e62-aaab-36cc20e32280/recovery-original-20261019`

Chave aleatória em pasta privada separada `recovery-original-keys`, fora do pacote,
Git, documentos e chat. Sem upload do backup para terceiros. A posse conjunta da
chave e do arquivo permite ler o conteúdo: mantê-los separados e protegidos.

## Dados incluídos na autorização solicitada

Perfis e IDs dos usuários (nome/e-mail/telefone e permissões, sem senha Auth),
clientes/contatos, unidades, categorias/culturas, produtos, funis e etapas,
oportunidades/itens/histórico, tickets, mensagens, notas internas, metadados e
conteúdo dos anexos privados, disparos/importações, outbox, auditoria e eventos de
integração. Configurações e webhooks de integração também podem conter segredos;
esses valores devem permanecer somente no backup privado cifrado.

Excluir dados de `app_sessions` e `user_invitations` (não recuperar sessões ou
convites antigos). Não exportar senhas/hashes de senha, tokens do Auth ou chaves
de API da plataforma. Não copiar `.env` por efeito deste procedimento.

## Procedimento revisável

1. Consultar o conjunto de registros em uma única leitura consistente no banco;
   salvar somente no diretório privado. Nunca imprimir registros/segredos.
2. Baixar os anexos referenciados, conferir tamanho e SHA256; registrar lacunas,
   sem apagar nada da origem. A captura de Storage não é uma transação de banco.
3. Cifrar o conjunto com `tools/recovery_bundle.py`, chave separada e manifesto
   de hashes autenticado. Não publicar backups/chaves/dados em pacote ou Git.
4. Restaurar os arquivos em pasta NOVA isolada, conferir hashes e reabrir o banco
   de ensaio local sem worker, callbacks ou acesso a clientes.
5. Documentar contagens e resultados sanitizados. Qualquer importação de dados
   reais em banco online ou restore no original exige decisão separada.

## Limite do ensaio já realizado

PGlite 0.5.10, PostgreSQL local em memória, sem URL de conexão externa.
Estrutura de26 tabelas/262 colunas/153 constraints/51 índices lida sem registros
de produção. Nove registros sintéticos, um arquivo sintético e dump reaberto.
Não inclui funções/triggers operacionais, login do Supabase/Auth, RLS de API,
Storage gerenciado ou restore de projeto Supabase. Isso ainda não fecha o ensaio
integral de recuperação do ambiente hospedado.

Os cinco testes do pacote cifrado e os nove checks locais passaram. Primeira
tentativa de exportação integral foi rejeitada pela revisão automática antes de
retornar dados; nenhuma exportação de registros de produção ocorreu.

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
