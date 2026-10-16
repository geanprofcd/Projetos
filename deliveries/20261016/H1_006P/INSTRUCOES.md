# H1-006O/P — saída humana e formulário idempotente STAGING

Aplicado e validado nesta cópia Windows. SQL13 e SQL15 aplicados separadamente no banco STAGING autorizado; SQL14/16 reversões preparadas, não executadas. O: humano real enviado sob demanda pelo Make até delivered, replay sem Send. P: texto sem anexos atômico/idempotente, nove verificações reais banco + oito HTTP comerciais, 280 testes Windows. Design preservado: somente inputs ocultos CSRF/request_id. Não houve promoção ao original físico, hospedagem ou habilitação de lote/worker automático. Make originais mantêm callbacks STAGING autorizados e filtros de envio bloqueados; cenário humano6654745 inativo/false.

Pacote cumulativo K/L/M/N/O/P. Não inclui segredos, perfis privados, estado, sessões, clientes ou objetos Storage. Instalador não executa SQL/Make, inicia processos ou habilita flags. Configuração privada desta sessão e estrutura de tabelas/bucket precisam existir separadamente; copiar arquivos não reproduz banco/contas/conexões/túnel.

Fonte: https://github.com/geanprofcd/Projetos/commit/3c274fcacc751fbe209e5bbe5fb7c249884bcf7a
Validação: https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_COMANDO_HUMANO_H1_006P.md
Mapa restante: https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/MAPA_HOMOLOGACAO_ORIGINAL.md
Envio humano: https://us2.make.com/292724/scenarios/6654745/logs/fd2aeee1a2844892b0cb11d7d741963f
Entregue: https://us2.make.com/292724/scenarios/6534261/logs/c4bf4dc8c62d4b18a291a3a48fc56420
Replay sem envio: https://us2.make.com/292724/scenarios/6654745/logs/638055adcf594956972751220c37cf51

Não é necessário reinstalar nesta sessão. Em outra cópia STAGING preparada:

```powershell
Get-FileHash -LiteralPath '.\VENDRA_H1_006P_HUMANO_ATOMICO_STAGING_20261016.zip' -Algorithm SHA256
Expand-Archive -LiteralPath '.\VENDRA_H1_006P_HUMANO_ATOMICO_STAGING_20261016.zip' -DestinationPath '.\H1_006P_CONFERENCIA'
powershell -NoProfile -ExecutionPolicy Bypass -File '.\H1_006P_CONFERENCIA	oolsplicar_callbacks_staging.ps1' -Destino 'CAMINHO_DA_COPIA_STAGING'
```

Último comando somente confere. -Aplicar copia diferenças com backup e rollback.json, exclusivamente no destino STAGING identificado. Preserva .env, runtime, .vendra-data e venv. SQL e reversão de banco são entregas separadas. Não aplicar SQL15 novamente no banco desta sessão.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.commercial_preview_start --config .env.h1_005b2 --check
powershell -NoProfile -ExecutionPolicy Bypass -File .	oolsalidar_staging.ps1
Invoke-RestMethod http://127.0.0.1:8013/health
```

Não iniciar instâncias duplicadas. Prévia8014 usa perfil privado explícito com controle persistente e transporte de disparos falso; o perfil base é preservado. Wake automático permanece desabilitado. Comandos acima não equivalem a homologação funcional de outro ambiente.

Falta H01: wake automático seguro, mídia/status por item, recuperação, padrão IA de novo atendimento. H02: criação/importação/lote comerciais. H03: backup/restauração e promoção seletiva. H04: original hospedado/HTTPS estável e limpeza final CODEX. Não excluir contas antes da homologação total; registros reais de envio devem ser preservados.
