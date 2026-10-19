# Mídias WhatsApp e continuidade do original

Fechamento documental em 18/10/2026. Implementação e testes em 16/10/2026; conferência Make repetida em 18/10/2026. O usuário autorizou explicitamente liberar mídias para clientes reais. Nenhuma campanha ou mensagem é iniciada por essa configuração.

## Aplicado e validado

Quatro arquivos backend promovidos seletivamente ao original Windows e à release Railway: app/services/whatsapp_media_service.py (novo), app/routers/tickets.py, app/whatsapp_callbacks.py e app/hosted_callbacks.py. Design, base, main e .env originais preservados. Backup output/backups/midia-original-20261016. Deploy abca256d-5fbc-4d3a-8fa0-a158f45ede37 SUCCESS.

SQL30 aplicado primeiro no STAGING e depois no original: quatro RPCs novas, EXECUTE somente service_role, sem novas tabelas ou policies. SQL31 é reversão preparada, não executada. O pacote só copia SQL; não o executa. Não reaplicar scripts históricos por conta própria.

Envio humano de JPEG/PNG, PDF, MP3/MP4 de áudio, OGG Opus e vídeo MP4 pelo formulário existente. Até seis arquivos, um WAMID/outbox por arquivo; texto opcional separado. Janela WhatsApp, perfil ativo, handoff humano e vínculo de destinatário continuam obrigatórios. Limites: imagem5MB, vídeo16MB, demais15MB no portal; OGG exige Opus. Não há transcodificação; vídeo de teste H264/AAC.

Reserva atômica e idempotente por comando; replay não duplica. Uploads privados e URL assinada temporária. Próximo item só sai após WAMID confirmado no banco. Resposta HTTP200 isolada não autoriza continuar. Resultado incerto mantém reserva claimed com aviso para revisão, sem reenvio automático. Isso exige análise operacional, não garante entrega de toda mídia.

Make humano6659974 recebe tipo e mídia dinâmica; destinatário agora é derivado da outbox autenticada, removendo o telefone de teste fixo. Tratamento de erro preserva a reserva e o cenário ativo. REV9 e Disparo Inicial não foram pausados. Somente cenário STAGING6665983 foi desligado após testes.

## Evidências

- 46 testes automatizados relevantes passaram no Windows com Python -X utf8.
- 16 verificações STAGING HTTP/banco/Storage: permissões, janela, reserva, replay, conflito, concorrência, URL privada, vínculo e resultado incerto. WAMID sintético nesse bloco não equivale a envio real.
- Quatro envios REAIS STAGING: PNG/PDF/MP3/MP4, cada um aceito pela Meta com WAMID real e tentativa única. Estado sent; entrega/read não comprovados nesse banco.
- Original: oito verificações, PDF pelo formulário com login real, tentativa única, status delivered confirmado no banco/feed. Modo anterior do atendimento restaurado. Evidências reais preservadas.
- Regressão online: oito páginas200, cinco colunas e Comercial sem acesso administrativo403.
- Publicação observada por180 segundos:148 observações de login/ponte, zero falhas. Não equivale a garantia futura de disponibilidade.

## Operação contínua

Os três cenários originais6534261,6561096 e6659974 estavam active e sem execuções incompletas na conferência de18/10. O original deve permanecer funcionando; não pausar para testes ou documentação. Usar STAGING e alterações seletivas, sem campanhas de teste não autorizadas.

Railway configurado com healthcheck /health, timeout120s, sobreposição30s e drenagem30s. Essas proteções reduzem interrupções nas trocas; não garantem disponibilidade absoluta. Referências: https://docs.railway.com/deployments/healthchecks e https://docs.railway.com/deployments/deployment-teardown .

Configuração vigente: VENDRA_BRIDGE_MEDIA_ENABLED=true no servidor e whatsapp_media.enabled=true, allowed_phones=[] no banco original. IA, resposta humana, disparos individuais e listas continuam habilitados. Segredos ficam privados, fora do pacote/Git.

## Segurança e pendências

Advisors dos dois projetos: INFO RLS habilitada sem policies para tabelas de backend (acesso service_role intencional); não abrir policies como atalho. https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy . WARN de proteção contra senhas vazadas do Auth desabilitada, não corrigido por esta entrega: https://supabase.com/docs/guides/auth/password-security . Não alegar ausência de alertas.

Recepção de mídias ainda pendente: REV9 atualmente aceita mensagens de texto. Gestão de modelos Meta no portal depende de credencial administrativa apropriada. Recuperação integral e carga de20mil contatos não têm comprovação. Não repetir fluxos homologados sem mudança relevante.

## Comandos e reversão

O original já está aplicado; nenhum comando é necessário para usar o portal. Teste opcional na cópia:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_whatsapp_media tests.test_whatsapp_human_bridge tests.test_whatsapp_human_command tests.test_hosted_callbacks tests.test_outbox_wake_guard tests.test_ticket_attention
```

Para reverter, coordenar primeiro Make e feature flags; restaurar backend seletivo pelo backup e só então avaliar SQL31. Não excluir mensagens, anexos ou WAMIDs reais. Nunca executar SQL31 enquanto os callbacks usam as novas RPCs. Não restaurar o telefone de teste fixo para clientes reais. Instalação do ZIP é separada de ativação/SQL e não modifica .env ou estado.
