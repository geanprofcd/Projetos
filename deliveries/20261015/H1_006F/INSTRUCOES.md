# H1-006F — Disparo Inicial persistente

Aplicado/testado no Windows STAGING. Cópia Make 6643860 sob demanda, sem webhook Meta. Seis casos de normalização passaram. Uma mensagem template autorizada enviada; WAMID e status delivered consistentes em dispatches/messages/whatsapp_outbox. Status real recebido no Make foi copiado ao auxiliar; recepção contínua e comando pelo portal/CRM ainda não homologados.

Fonte: https://github.com/geanprofcd/Projetos/commit/f4398e80980c119d481e8c1d281fd7cf60c2ee7e
Validação: https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_DISPARO_INICIAL_STAGING.md
Envio: https://us2.make.com/292724/scenarios/6643860/logs/3513da070690451583c8f83f25697b49
Delivered: https://us2.make.com/292724/scenarios/6640168/logs/a20b70bdab784504be63af41e5cde7aa

200 testes Windows em cópia limpa (1,703 s), 43 focados e 22 verificações HTTP/Supabase com oito conexões independentes aprovados. SQL de correção coberto por reteste direcionado real. Flag temporária removida, fixtures sintéticas limpas; evidência real de envio preservada. Cópias inativas e filtro de template bloqueado. Nenhuma promoção ao original.

Sete arquivos gerenciados e manifesto SHA256. Código aplicado nesta sessão; não é necessário reinstalar. Para outra cópia preparada, conferir/extrair em pasta nova:

```powershell
Get-FileHash -LiteralPath '.\VENDRA_H1_006F_DISPARO_STAGING_20261015.zip' -Algorithm SHA256
Expand-Archive -LiteralPath '.\VENDRA_H1_006F_DISPARO_STAGING_20261015.zip' -DestinationPath '.\H1_006F_CONFERENCIA'
powershell -NoProfile -ExecutionPolicy Bypass -File '.\H1_006F_CONFERENCIA\tools\aplicar_callbacks_staging.ps1' -Destino 'CAMINHO_DA_COPIA_STAGING'
```

Último comando é dry-run; -Aplicar aplica somente o delta com backup e rollback.json. Não toca .env/estado/venv. Rollback de código restaura somente caminhos registrados e remove apenas arquivos novos registrados, sem reverter dados/SQL/Make por efeito colateral.

SQL é operação separada. Somente STAGING recebeu migrations vendra_dispatch_control_bind_v1 e vendra_dispatch_message_wamid_fix_v1, após autorização. Em outro STAGING, revisar pré-requisitos H1-006B, aplicar SQL06 e depois SQL08 com ferramenta de migration autorizada. SQL07 desconecta/remove as três funções sem apagar dados; não executar por instalar este pacote. Original não recebeu migrations.

Novo perfil exige VENDRA_BRIDGE_DISPATCH_ENABLED=true para registrar rotas; padrão false. Configuração global dispatch_bridge.enabled também é necessária para reserva; o instalador não a cria. Não inclui perfis, segredos, payloads de teste ou backups Make. Ponte não envia diretamente ao provedor.

Teste focado na raiz do runtime preparado:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_whatsapp_callbacks tests.test_whatsapp_control_bridge tests.test_whatsapp_dispatch_bridge -q
```

Checkout Git separado, preservando alterações locais:

```powershell
$repo = 'C:\Users\israe\Downloads\Automações\VENDRA-GIT-STAGING'
git -C $repo fetch origin
if (git -C $repo status --porcelain) { throw 'Revisar alterações locais antes de sincronizar' }
git -C $repo pull --ff-only
```

O usuário reforçou autorização para trabalho integrado e cópias necessárias, sem pausar após atualizar o Mestre. Próxima etapa em andamento: recepção contínua isolada e integração portal/CRM. Criação do app Meta de teste solicitada; Meta pediu reautenticação da sessão, pendente de conclusão pelo usuário. Callback original preservado. Não declarar app criado ou fluxo integral homologado antes da evidência.
