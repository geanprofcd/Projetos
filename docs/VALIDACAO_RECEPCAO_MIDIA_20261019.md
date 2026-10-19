# Recepção de mídia - STAGING, 19/10/2026

## Situação vigente

Implementação e validação na cópia Windows/STAGING. **Não promovida ao principal**: banco original, pasta original, Railway e cenários originais preservados. Envio de mídias em produção da v1.59 continua funcionando. Falta confirmar um arquivo realmente enviado pelo WhatsApp de teste e, depois, autorizar separadamente SQL32/ativação do ramo de recepção no original.

## Código e contrato

Novo app/whatsapp_inbound_media.py; ajustes em app/whatsapp_callbacks.py e app/hosted_callbacks.py. Flag VENDRA_BRIDGE_INBOUND_MEDIA_ENABLED=false por padrão, independente do envio. Rota autenticada POST /webhooks/make/whatsapp/media, somente no ambiente que habilitar explicitamente a flag. Mesmo segredo, conta/remetente e escopo de telefone obrigatórios. Corpo de mídia até23MiB antes do parse; demais callbacks continuam64KiB. Segredo é validado antes de ler o corpo grande, erros não reproduzem conteúdo de arquivo.

Mídias suportadas neste contrato: JPEG/PNG5MiB, PDF/TXT15MiB, MP3/M4A/OGG-Opus/MP4 até16MiB. SHA256 da Meta deve coincidir com o conteúdo baixado. MIME/assinatura/tamanho conferidos, nome saneado e extensão derivada do formato. Não há transcodificação, antivírus, transcrição de áudio ou análise de imagem pela IA neste bloco.

Storage privado ticket-attachments; nome determinístico por hash do WAMID e do conteúdo, sem upsert. Repetição só reutiliza objeto se conteúdo confere. SQL32 chama a recepção de texto existente e grava vínculo do anexo/evento na MESMA transação de banco, preservando atividade, janela WhatsApp, regra Novo Lead->Qualificação e ativação de IA por resposta após disparo. Objeto Storage e banco não fazem uma transação distribuída: rejeição definitiva remove só objeto sem vínculo; resultado incerto preserva arquivo para repetir o MESMO evento. Nunca reenviar WhatsApp para resolver uma confirmação de banco.

Mídia é exibida nos controles comerciais existentes. Somente o evento binário para antes do módulo de IA; modo IA/humano do atendimento fica preservado para mensagens seguintes. A IA não deve inventar conteúdo a partir de um marcador de arquivo.

## SQL aplicado somente no STAGING

Usuário autorizou explicitamente SQL32 somente no projeto ljufhqnadzltqbtdaulv. Migration vendra_whatsapp_inbound_media_v1 aplicada. Uma nova RPC public.vendra_whatsapp_media_receive_v1, SECURITY INVOKER/search_path vazio; anon=false, authenticated=false, service_role=true. Não altera tabelas/RLS ou funções anteriores. Script33 de reversão preparado, não executado; desabilitar a rota e retirar o ramo de mídia no destino antes de remover a RPC. Não pausar os cenários originais de texto para isso.

## Evidências funcionais e limites

- 52 testes locais Windows passaram, incluindo autenticação, limites, checksums, MIME com parâmetros, timestamp, conflitos, preservação após resultado incerto, privacidade do erro e regressão dos callbacks de texto/saída humana.
- 18 verificações reais HTTP/banco/Storage/portal STAGING: mensagem+anexo, Novo Lead->Qualificação, modo humano, replay, conflito, concorrência (um novo/um duplicado), Comercial/feed, escape da legenda, URL assinada/conteúdo, acesso público e sem sessão bloqueados, texto preservado e zero outbox. Repetição final após as proteções não é um novo bloco de18 testes distintos.
- Cópia Make6689575 sob demanda, conexão Israel existente11704121, sem webhook Meta e SEM módulo Send. Quatro arquivos próprios foram enviados ao armazenamento da Meta, baixados e gravados pela ponte STAGING. Conteúdos e hashes PNG/PDF/MP3/MP4 conferidos com originais. **Não equivale a quatro mensagens recebidas de um lead**; WAMIDs desse bloco são sintéticos.
- PDF349d6e92bc88405bb1ba63dde2b58e40; PNG e8619a04380348a5b4702f52ecfab094; MP3 bd933f0699c2438ebd65d0ca88667eb0; MP4 53dc06d859204cb0b45d23468a21be35.
- Cópia final sem módulo Upload: recebe ID de mídia e metadados, baixa pela conexão Meta e persiste. Mesmo evento em2fc01ff7836b487cb9a5b987dd6b91df e f8bdb1e7e1f74b4e808a656e69fd87e4 retornou exatamente os mesmos IDs de mensagem/anexo, sem duplicar. Fonte ainda arquivo próprio, não webhook real.
- Fixtures sintéticas removidas; clientes preexistentes e evidências WhatsApp reais anteriores preservados. Nenhum WhatsApp enviado nesta rodada. Tokens e segredo do túnel fora de Git/pacote.

## Próximo passo indispensável

Solicitado ao usuário pelo número87988216094 um PDF pequeno ou imagem ao Israel, legenda “Teste mídia VENDRA”. Localizar o evento REAL no Make, conferir remetente/conta, copiar somente esse evento para o STAGING e validar o arquivo no chat. Não reprocessar mensagens de outros clientes para o STAGING. Esse teste ainda está pendente; não marcar recepção contínua homologada.

Somente após isso, preparar alteração seletiva do ramo de mídia no REV9 original, com backup e retorno aos callbacks Railway, obter autorização específica do SQL original/ativação e conferir o caminho hospedado. Não substituir fluxos de texto/IA/status ou cenários inteiros. O original deve continuar funcionando.

## Segurança e operação

Advisors STAGING após SQL: INFO RLS sem policy em tabelas exclusivas de backend e WARN preexistente de proteção contra senhas vazadas desabilitada. Não foram abertas policies ou ampliadas permissões públicas. Referências: [RLS sem policy](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy), [proteção de senhas](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

Changelog Supabase consultado antes da implementação: avisos de TLS/CBC e ltree não exigem alteração no contrato de upload utilizado. Documentação primária: [upload privado](https://supabase.com/docs/reference/python/storage-from-upload) e [URL assinada](https://supabase.com/docs/reference/python/storage-from-createsignedurl).

Comando de verificação na cópia, sem envio externo:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_whatsapp_inbound_media tests.test_whatsapp_callbacks tests.test_whatsapp_human_bridge tests.test_hosted_callbacks tests.test_whatsapp_media
```

Não há comando a executar no principal nesta etapa. Não aplicar SQL32/33 no original por efeito do pacote. Gestão Meta no portal, restauração integral, carga de20mil, proteção Auth e limpeza CODEX final continuam separados e pendentes.

Ao encerrar esta rodada, somente a copia Make6689575 foi deixada inativa e os processos proprios de ponte/tunel8013 foram encerrados. Arquivo real ainda pode chegar ao gatilho Meta original; para validar no STAGING, reabrir somente a ponte/copia de teste e renovar seu callback. Os tres cenarios originais permanecem ativos. Conferencia por hash:131 arquivos app do original Windows seguem identicos a release hospedada anterior; nenhum backend de recepcao foi promovido.
