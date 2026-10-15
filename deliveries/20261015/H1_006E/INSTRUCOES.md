# H1-006E — IA, contratos e saída controlada

Aplicado/testado no Windows STAGING. Rota normal com agente/Knowledge, resposta e outbox comprovada; replay e handoff passaram. Um envio real ao destinatário autorizado, WAMID vinculado e evento Meta delivered persistido. O status real foi copiado do cenário receptor para o auxiliar; recepção contínua isolada ainda não homologada. Leitura não comprovada. Original preservado; nenhum servidor permanente confirmado.

Fonte: https://github.com/geanprofcd/Projetos/commit/782e16de160cd374f12b81284cd7e9ce4f49e11f
Evidências: https://github.com/geanprofcd/Projetos/blob/desenvolvimento/vendra-staging/docs/VALIDACAO_AGENTE_CALLBACKS_STAGING.md
Envio: https://us2.make.com/292724/scenarios/6639761/logs/24df24dec9524938a7505d492863b969
Status: https://us2.make.com/292724/scenarios/6640168/logs/e9ed18e094314d929be69aa5242d9a59

Três arquivos gerenciados, manifesto SHA-256 e instalador com backup. Nenhum segredo/perfil/payload pessoal/backup Make. Pacote de código não executa SQL, altera Make, inicia processo/túnel nem envia mensagens. Copiar configurações SaaS é uma operação separada. Nenhuma promoção ao principal.

Na cópia desta sessão já aplicada não é necessário reinstalar. Em outra cópia STAGING preparada, conferir e extrair em pasta nova:

```powershell
Get-FileHash -LiteralPath '.\VENDRA_H1_006E_IA_CALLBACKS_STAGING_20261015.zip' -Algorithm SHA256
Expand-Archive -LiteralPath '.\VENDRA_H1_006E_IA_CALLBACKS_STAGING_20261015.zip' -DestinationPath '.\H1_006E_CONFERENCIA'
powershell -NoProfile -ExecutionPolicy Bypass -File '.\H1_006E_CONFERENCIA\tools\aplicar_callbacks_staging.ps1' -Destino 'CAMINHO_DA_COPIA_STAGING'
```

Último comando é somente dry-run. Acrescentar -Aplicar aplica apenas delta, gera backup e rollback.json. Para rollback, restaurar somente caminhos registrados e remover somente arquivos novos registrados, preservando estado/segredos; não executar SQL ou reverter cenários por efeito do rollback de código.

Ferramenta de contrato: executar a partir da raiz como módulo, usando Python -X utf8. Ver pré-condições e isolamento no documento de evidências. Sem --executar apenas verifica; com --executar cria configuração/fixtures temporárias no STAGING fixado e exige isolamento dos consumidores públicos.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.whatsapp_callbacks_contract_check --config 'PERFIL_PRIVADO_8012' --resposta-agente 'RESPOSTA_PRIVADA.txt' --relatorio 'RELATORIO_PRIVADO.json'
```

O relatório real anterior contém 18 checks aprovados e limpeza confirmada; seis callbacks Make, 188 testes Windows e 31 focados compõem as evidências. A publicação não significa repetição dessas suítes. Pré-flight CLI somente leitura conferido nesta entrega. Testes sem mudança não serão repetidos gratuitamente.

Cópias Make inativas, filtros constantes de envio restaurados, flag global removida. Atendimento de teste real encerrado em modo humano e suas evidências preservadas. Fixtures sintéticas removidas. Contas CODEX só serão excluídas ao final da homologação total.

Plano acelerado: (1) integração sem envio comprovada; (2) concluir cópia Disparo Inicial e recepção contínua isolada, aproveitando saída real REV9 já entregue; (3) infraestrutura estável, homologação final, promoção seletiva com backup/rollback e limpeza. Não confundir entrega manual de status com callback contínuo homologado.
