# Original local e original hospedado: integração

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
| Transmissão de áudio/imagem/PDF/vídeo pelo WhatsApp | **Pendente** | Armazenar no portal não envia pelo WhatsApp. Reserva humana atual retorna media_contract_required; requer contrato por item/WAMID e integração Make/Meta |
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
