# H1-006B | Entrega SQL separada

Migration aplicada exclusivamente no VENDRA-STAGING com autorizacao especifica. 27 verificacoes transacionais remotas aprovadas, encerradas com ROLLBACK; dados reais preservados e IA desligada. Nenhum Python, Make ou processo alterado. Nenhum reinicio necessario. Nao reaplicar 03 no banco ja migrado. Leia docs/WHATSAPP_CONTROLE_SAIDA_STAGING.md para limites e proxima etapa.

Conferir e extrair em pasta nova (PowerShell, na pasta do download):

```powershell
Get-FileHash -LiteralPath '.\VENDRA_H1_006B_SQL_STAGING_20261014.zip' -Algorithm SHA256
Expand-Archive -LiteralPath '.\VENDRA_H1_006B_SQL_STAGING_20261014.zip' -DestinationPath '.\H1_006B_SQL_CONFERENCIA'
$pkgPath = (Resolve-Path '.\H1_006B_SQL_CONFERENCIA').Path
$manifest = Get-Content (Join-Path $pkgPath 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    if ((Get-FileHash -LiteralPath (Join-Path $pkgPath $entry.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw 'Hash divergente' }
}
```

Arquivos novos ja presentes na copia Windows de desenvolvimento. O pacote apenas arquiva SQL/documentacao; nao executa SQL ou instala servicos. Para outra copia, mantenha a extracao separada e faca backup de qualquer arquivo homonimo antes de copiar. 04 pode ser executado manualmente no SQL Editor somente do STAGING e termina em ROLLBACK. 05 e rollback preparado, nao executado; exige consumidores H1-006B desligados. Nao inclui perfis, segredos, bancos ou dados locais. Codigo original/principal preservado; checkout da nuvem sem sincronizacao comprovada. Funcionalidade IA completa ainda nao homologada.

Projeto: https://supabase.com/dashboard/project/ljufhqnadzltqbtdaulv/sql/new
Proxima etapa: endpoints autenticados e limitados por entidade/destinatario, concorrencia por conexoes independentes e adaptacao Make antes do teste real de IA.
