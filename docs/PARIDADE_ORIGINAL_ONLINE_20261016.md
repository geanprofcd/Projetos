# Original local e original hospedado: integração

## Desenvolvimento v1.60 - 19/10/2026 (somente STAGING)

Recepção de mídia implementada e validada com52 testes Windows,18 verificações funcionais e quatro arquivos próprios pela cópia Make. Ainda falta evento real do WhatsApp e promoção/SQL autorizados para o original. Produção permanece na v1.59, envio de mídias/texto/IA/disparos preservados; os três cenários originais não foram pausados. Ler [VALIDACAO_RECEPCAO_MIDIA_20261019.md](VALIDACAO_RECEPCAO_MIDIA_20261019.md). Não contar upload/download de arquivo próprio como recepção real de lead.


## Estado vigente v1.59 - 18/10/2026

Envio de mídias liberado para clientes reais após autorização específica. PNG/PDF/MP3/MP4 aceitos em teste real STAGING; PDF delivered pelo portal original. Quatro arquivos backend e SQL30 promovidos seletivamente. Deploy abca256d-5fbc-4d3a-8fa0-a158f45ede37. Os três cenários originais Make permanecem ativos: não pausar para desenvolvimento/testes. Recebimento de mídias e gestão Meta pelo portal continuam pendentes. Evidência, limites, segurança e reversão: [VALIDACAO_MIDIA_WHATSAPP_20261016.md](VALIDACAO_MIDIA_WHATSAPP_20261016.md). Seções anteriores a este checkpoint são históricas; pendência antiga de envio de mídia está encerrada.


Atualizado em 16/10/2026. Esta matriz substitui listas históricas de pendências; não declara que páginas HTTP200 equivalem a homologação completa de todas as ações.

## Levantamento executado

Comparação por SHA256 de **130 arquivos em app**, excluindo bytecode: original Windows e release privada hospedada idênticos, nenhum arquivo faltante. **104 rotas comerciais/administrativas catalogadas** nos routers nativos, excluindo routers de diagnóstico STAGING. **15 páginas** com login administrativo real abriram com HTTP200: início, clientes/lista/novo, atendimentos/lista/funil, oportunidades, produtos/lista/novo, indicadores, disparos, usuários, integrações, auditoria, configurações e funis.

Os dados locais não foram copiados. O estado demo contém clientes, senhas, filas e exemplos. Os dois produtos Consultoria/Implantação têm descrições demonstrativas no código original; não foram introduzidos como produtos reais de produção. Funil comercial e motivos de perda já haviam sido recuperados separadamente da configuração original na SQL25.

## Recursos presentes e integrações

| Recurso do original | Situação online | Evidência e limite |
|---|---|---|
| Design, navegação e telas comerciais | Integrados | 130 arquivos iguais; layout/base/CSS preservados |
| Clientes e catálogo | Integrados | Leitura/cadastro existentes no banco real; catálogo começa sem os produtos demo |
| Funis, cards, valores e histórico | Integrados | Cinco etapas originais, 38 verificações funcionais anteriores STAGING +38 online; não repetidas nesta rodada |
| Recepção de texto, IA e resposta humana | Integrados | Fluxos reais e READ anteriores, callbacks hospedados |
| Disparo inicial individual e por lista | Integrados | Canal regular autorizado, quantidade/fila hospedadas; nenhum novo disparo nesta rodada |
| Regras de Qualificação, Proposta e controle IA | Integradas | SQL28, rodada real Calendly com envio único/READ, pausa Comercial preservada |
| Alertas de 30 minutos | Integrados | Correção claimed, STAGING funcional e rota online já conferidos |
| Indicadores, auditoria, configurações e permissões | Código/rotas integrados | Páginas200; permissões funcionais já verificadas. Não simular indicadores a partir de dados demo |
| Arquivos e notas internas com anexos | Integrados nesta rodada | Bucket privado faltava no original; criado e testado pelo formulário/Storage/banco reais |
| Convite para equipe sem SMTP | Integrado nesta rodada | Link de uso único/48 horas, aceite cria conta real, login e perfil Comercial conferidos |
| Transmissão de áudio/imagem/PDF/vídeo pelo WhatsApp | **Envio integrado v1.59** | Reserva/WAMID por arquivo; quatro formatos aceitos STAGING e PDF delivered original. Recepção de mídia ainda pendente |
| Gestão de modelos Meta dentro do portal | **Pendente de credencial** | Código original usa META_ACCESS_TOKEN; token ausente tanto no .env original local quanto na configuração disponível. Templates fixos de disparo pelo Make já funcionam |

## Convites por link: alternativa ao e-mail

Configurado INVITATION_DELIVERY=link e PUBLIC_APP_URL=https://vendra-original-production.up.railway.app. Em Usuários, o administrador gera o convite e copia o link mostrado no aviso existente. Compartilhamento é feito pelo administrador; o VENDRA não envia e-mail ou WhatsApp automaticamente. Convidado define a própria senha; validade48h, uso único, hash no banco. Nova emissão revoga links anteriores pending/sent do mesmo endereço. Delegação não permite elevar privilégios. Páginas com link usam no-store e no-referrer.

Quatro testes automatizados de convites, mais14 dos serviços afetados passaram. STAGING:13 verificações com banco/Auth reais, criação/aceite/login/perfil/negação de administração, reuso e elevação bloqueados. Original:9 verificações reais do formulário/aceite/login/permissões; sem e-mail. Contas CODEX exclusivas inativadas, banidas e sessões revogadas; convites temporários removidos. Exclusão definitiva das contas CODEX segue a limpeza final acordada. Um smoke demo auxiliar ficou sem progresso e foi interrompido; não consta como aprovado. A evidência funcional é a execução real do STAGING e do original.

## Arquivos privados

Bucket ticket-attachments, public=false, limite52428800 bytes. Backend conserva limite15MB geral/50MB vídeo e validação de conteúdo. STAGING:9 verificações reais no formulário. Original:10 verificações incluindo upload, vínculo/checksum, download assinado, bloqueio público, rota sem sessão protegida e feed. Objetos/metadados/cliente/atendimento exclusivos removidos ao final. Nenhuma outbox criada ou mensagem externa enviada.

Não foi alterada policy/RLS de tabelas. O bucket usa backend service_role e URLs assinadas existentes. Criar o bucket não reativa campanhas ou transportes. Para eventual reversão, não apagar um bucket com arquivos reais; primeiro inventariar/exportar. O bucket não está em scripts SQL automáticos.

## Aplicação

Quatro arquivos seletivos: config.py, user_service.py, routers/users.py e templates/users/index.html. O template apenas aproveita o aviso existente para mostrar o campo de link; não troca estrutura, CSS ou navegação. Backup original output/backups/convites-original-20261016; .env/main/base preservados por hash. Release80d933b4 publicou o código; deploy68d979f1-19c5-4631-b039-32c83dac3648 SUCCESS ativou a URL pública e modo link. Nenhuma modificação dos cenários Make nesta rodada.

## Próxima integração necessária

Fechar mídia com reserva idempotente, identificação e status por arquivo, tratamento de falhas e teste real limitado ao destinatário já autorizado. Não remover o bloqueio media_contract_required como atalho, nem alegar que upload no portal significa entrega. Modelos Meta exigem credencial administrativa específica; a conexão WhatsApp existente do Make continua responsável pelos envios de texto e templates homologados. Recuperação integral de banco e carga de20mil contatos continuam sem comprovação; isso não é funcionalidade removida do modelo local.

Comando opcional na cópia Windows:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_user_invitation_link tests.test_ticket_attention tests.test_conversation_order
```

Não há comando necessário para usar o original já atualizado. Não reaplicar SQL ou copiar estado local/demo para produção.

## Atualização19/10 — v1.61
Recepção de mídia: SQL32 original autorizado/aplicado, backend e ramo85/86+handlers87/88 ativos no Railway/REV9, healthinboundtrue. Teste automático de novo arquivo solicitado/pendente. Scroll interno sem barra vertical publicado. Evolução10.000cards aprovadaSTAGING (17verificações/74Windows), SQL34somenteSTAGING; promoçãoSQL34originalaguardaautorizaçãoespecífica. Não pausar cenários originais. Ver VALIDACAO_ROLAGEM_FUNIS_20261019.md e VALIDACAO_RECEPCAO_MIDIA_20261019.md.

### Recepção automática original concluída — estado mais recente19/10/2026
Run be3add398da242f18a94b5033408e40b, iniciado00:08:11.930Z20/10 (=21:08Brasília19/10), AUTO, sucesso4,603s/3operações/3créditos. Módulos71/85/86, uma invocação cada, zero erros; nenhum módulo de envio. Callback202accepted/media_storedtrue/duplicatefalse. Nove verificações reais no original: remetente/conta, WAMID gravado, vínculo único, hashMeta, loginadministrativo hospedado, chat, feed, download privado e arquivo completoSHA256. Evidência real preservada. Recepção automática hospedada homologada; solicitação de arquivo final atendida. Pendência separada permaneceSQL34original/paginação10k, não autorizada ainda.
