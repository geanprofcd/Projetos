# VENDRA — acompanhamento e correção UTF-8

## Resumo desta atualização

- **Aplicado na nuvem:** instalador corrigido para executar Python com `-X utf8`, preservando aplicação, template e testes.
- **Validação:** 157 testes aprovados na nuvem. O log Windows anterior mostra 156 aprovações e um erro CP1252 na leitura de template UTF-8.
- **Etapa atual:** confirmar os 157 testes no Windows e depois homologar o fluxo funcional no STAGING. O principal permanece inalterado.

As próximas entregas também incluirão resumo breve e links, conforme solicitado pelo usuário.

## Links da entrega corrigida

- [Baixar pacote ZIP corrigido](https://github.com/geanprofcd/Projetos/raw/refs/heads/entregas/staging-20261014/entregas/VENDRA_STAGING_ACOMPANHAMENTO_20261014_UTF8.zip)
- [Página do pacote no GitHub](https://github.com/geanprofcd/Projetos/blob/entregas/staging-20261014/entregas/VENDRA_STAGING_ACOMPANHAMENTO_20261014_UTF8.zip)
- [Instalador UTF-8 avulso](https://github.com/geanprofcd/Projetos/raw/refs/heads/entregas/staging-20261014/entregas/ATUALIZAR_COPIA_TESTES_UTF8.ps1)

O [pacote anterior](https://github.com/geanprofcd/Projetos/raw/refs/heads/entregas/staging-20261014/entregas/VENDRA_STAGING_ACOMPANHAMENTO_20261014.zip) foi preservado.

## Repetir os testes já instalados

Na janela PowerShell, usar a pasta de verificação do backup indicada no erro:

```powershell
$base = 'C:\Users\israe\Downloads\Automações\VENDRA_v0.0.4_Windows_Source\VENDRA_v0.0.4_Windows - Copia'
Set-Location -LiteralPath (Join-Path $base 'vendra_starter_backup_cloud_20261014_093542\verificacao')
& (Join-Path $base 'vendra_starter\.venv\Scripts\python.exe') -X utf8 -m unittest discover -s tests -p 'test_*.py' -v
```

Isso não reaplica arquivos nem reinstala dependências. Resultado esperado: `Ran 157 tests` e `OK`. Enviar a saída antes de considerar essa etapa validada. A falha anterior já tinha preservado backup e registro; não apagá-los.

## Aplicar o pacote corrigido

Extraia o ZIP corrigido em uma pasta separada, por exemplo `C:\Users\israe\Downloads\Automações\VENDRA_UTF8`. Pare somente STAGING 8011 e execute:

```powershell
powershell.exe -NoProfile -File 'C:\Users\israe\Downloads\Automações\VENDRA_UTF8\ATUALIZAR_COPIA_TESTES.ps1' -Aplicar
```

Siga também `LEIA_PRIMEIRO.txt`. O script preserva configurações e dados, faz backup e executa testes. Não aplica SQL, ativa Make ou promove ao principal.

Startup posterior, após aprovação dos testes, no diretório real `vendra_starter`:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.staging_start
```

O instalador avulso pode substituir apenas a rotina de execução quando colocado junto ao `MANIFEST.json` e `payload` da extração anterior. Não executá-lo em pasta sem esses arquivos. A homologação funcional e os testes reais Windows com a correção continuam pendentes.

SHA-256 do ZIP corrigido: `0e7c4749d5d9da046686f1c0653968d5b163681912fda72108b6791cdb322203`.
