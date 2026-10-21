# VENDRA v1.64 — recuperacao local, backup externo e copia VENDAXIS

ESTE PACOTE CONTEM SOMENTE ferramentas e documentacao sanitizada. Nao contem backup real, chave, registros de clientes, .env, credenciais, schema capturado ou fontes comerciais privadas do VENDAXIS. Nenhum deploy do original foi alterado para esta entrega.

Executado: backup cifrado AES-256-GCM de24tabelas/452registros/2anexos, restauracao local de integridade aprovada. Cifrado salvo na pasta Drive indicada e hash conferido por download. Chave NAO foi enviada e ainda precisa de custodia independente doPC, separada do cifrado. Nao e restauracao integral dos servicos Supabase/Auth/Storage/funcoes.

VENDAXIS:145arquivosbaseline da release original,5adaptacoes tecnicas de isolamento sem alterar telas/CSS/regras comerciais.8testes isolamento/6checks schema locais passaram. Copia e ZIP ficam somente no Windows, em Downloads/Automacoes/VENDAXIS_20261020. Usuario decidiu manter apenas local apos limite de2projetos gratuitos; nenhumbackend/criacaodeadminonline/cenarioMake/contratacao efetuado. Mesma credencial administrativa preparada fora do repositorio, em arquivo privado.

Instalacao de ferramentas em outra COPIA STAGING, opcional:

```powershell
python -X utf8 aplicar.py --destino "C:/CAMINHO/COPIA_STAGING/vendra_starter"
python -X utf8 aplicar.py --destino "C:/CAMINHO/COPIA_STAGING/vendra_starter" --aplicar
python -m pip install -r tools/requirements-recovery.txt
python -X utf8 -m unittest tests.test_recovery_bundle
```

Instalador confere hashes e backup dos arquivos alterados. Recusa aplicacao em perfis do original. Nao executa SQL, nao coleta banco e nao acessa rede. Dependencia cryptography50.0.2 testada no ambiente local; nao adicionada ao deploy do VENDRA.

Comandos para arquivos previamente revisados, em ambiente privado:

```powershell
python -X utf8 -m tools.recovery_bundle seal --source "PASTA_PRIVADA_REVISADA" --archive "PASTA_BACKUP/snapshot.vrb" --key "OUTRA_PASTA/key.bin"
python -X utf8 -m tools.recovery_bundle restore --archive "PASTA_BACKUP/snapshot.vrb" --key "OUTRA_PASTA/key.bin" --destination "PASTA_NOVA_ISOLADA"
```

Nunca publicar a chave, sobrescrever ambiente existente ou usar esses comandos como autorizacao para copiar dados reais de outro destino. Arquivo cifrado e chave devem ficar separados. Documentacao de pendencias em files/docs/PENDENCIAS_ATUAIS_VENDRA.md; evidencia/limites em files/docs/VALIDACAO_RECUPERACAO_20261019.md. Copia VENDAXIS detalhada em files/docs/COPIA_LOCAL_VENDAXIS_20261020.md.
