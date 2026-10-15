# VENDRA H1-006A - callbacks STAGING

Delta aplicado e validado na copia Windows de testes. Nao aplicar no VENDRA original.
170 testes Windows e 21 verificacoes reais Supabase aprovados; entrada real e status via Make persistidos.
IA, worker, saida automatica e promocao permanecem fora desta entrega.

## Verificar/aplicar
Extraia o ZIP e execute na pasta extraida:
~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\aplicar_callbacks_staging.ps1 -Destino "CAMINHO_DA_COPIA_STAGING"
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\aplicar_callbacks_staging.ps1 -Destino "CAMINHO_DA_COPIA_STAGING" -Aplicar
~~~
Instalador verifica SHA-256 e perfil STAGING; faz backup de arquivos substituidos e registra arquivos novos.
Nao executa SQL, configura credenciais, inicia servicos/tunel, altera Make ou envia mensagens.

## Testar/iniciar
Na copia STAGING instalada:
~~~powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_whatsapp_callbacks -v
.\.venv\Scripts\python.exe -X utf8 -m tools.whatsapp_callbacks_start --config "CAMINHO_PRIVADO\whatsapp_bridge_staging.env" --port 8012
~~~
Perfil privado precisa de credenciais proprias STAGING, remetente Meta e destinatarios autorizados.
Perfil desta sessao e backups Make NAO estao no pacote.
Leia docs/WHATSAPP_CALLBACKS_STAGING.md para contrato, verificacoes, rollback e limites.

## Banco, promocao e nuvem
SQL aplicado separadamente somente em VENDRA-STAGING. Copiar arquivos nao executa migrations.
Nao executar novamente a criacao de funcoes existentes; nao aplicar preflight de STAGING em producao.
Nao houve atualizacao comprovada do checkout da nuvem nem promocao ao principal.
Publicacao do ZIP na branch de entregas e distribuicao, nao aplicacao remota.
Restaurar arquivos pelo backup/rollback.json; nunca copiar .env, runtime, sessoes ou estado entre ambientes.
Rollback SQL separado preserva dados/tabelas/RLS e exige desconectar o consumidor antes.

## Limites funcionais
Entrada real e sent/delivered persistidos. Status do envio auxiliar ficam pending_match, sem outbox VENDRA.
Vinculo/reconciliacao automatica, controle IA e fluxo completo ainda pendentes.
Tunel de teste temporario. Hospedagem deve usar origem HTTPS estavel, mesmos contratos e segredos por ambiente.