# VENDRA — pendências vigentes em 21/10/2026

Pendência imediata: publicar o feedback visual da importação já homologado e aplicado ao original local. Railway informou incidente oficial de API/builds pausados; tentativa de deploy recusada. Ainda não está na versão hospedada. Ver VALIDACAO_IMPORTACAO_LISTAS_20261021.md. Portal e health seguem200.

Este quadro substitui as listas antigas de pendências; o histórico permanece nos
relatórios e no Mestre. Sistema original online no Railway, sem dependência de
túnel local para as conversas/disparos. Não pausar o Make para desenvolvimento.

## Já concluído

- Login e perfis Administrativo/Comercial, UX/UI comercial e funil de cinco etapas.
- Conversas WhatsApp com IA/humano, pausa manual, Qualificação/Proposta/Calendly,
  ordenação por atividade e alerta de30min sem resposta.
- Disparo individual e fila por lista, com quantidade selecionável.
- Envio e recepção de mídias, vínculo ao chat, arquivo privado e status de envio.
- Colunas com rolagem interna, barras verticais ocultas e janela de120cards;
 10.000cards no STAGING/17checks e13 verificações hospedadas Comercial aprovados.
- Convites por link sem dependência de SMTP.
- Backup cifrado local autorizado:24tabelas/452registros/2anexos; restauração local
 de integridade aprovada. Backup/chave fora do Git; cópias temporárias em claro removidas.

## O que falta, na ordem recomendada

| Prioridade | Pendência | Critério de conclusão / dependência |
|---|---|---|
| 1 | Custódia independente da chave do backup | Cifrado já salvo no Drive indicado e SHA256 conferido por download. Falta guardar a chave fora deste computador em local controlado e separado do arquivo. Nenhuma recorrência criada. |
| 2 | Recuperação integral dos serviços | Em ambiente separado autorizado, reconstituir funções/triggers/permissões, Auth e Storage gerenciado e conferir login/conversa/arquivos sem envios. O ensaio local atual cobre dados/arquivos/constraints, não o projeto Supabase completo. |
| 3 | Gestão de modelos Meta dentro do portal | Configurar privadamente credencial com permissões apropriadas e homologar consulta/criação/status. Em20/10 o endpoint hospedado modelos.json retorna configured=false. Os templates existentes do Make continuam funcionando. |
| 4 | Concorrência operacional complementar | Importação/leitura de20.000contatos, oito inícios simultâneos da mesma fila e oito reservas simultâneas da mesma linha pelo mesmo ator passaram no STAGING em21/10; um pedido, zero envios e fixtures removidas. Falta, se necessário à homologação final, concorrência de usuários autenticados/claims e processamento prolongado com transporte suprimido. Não enviar20.000mensagens como teste ou prometer SLA. |
| 5 | Proteção Auth contra senhas vazadas | Aviso confirmado em20/10. Conferir elegibilidade e ativação; a documentação Supabase exige Pro ou superior. Não contratar upgrade automaticamente. |
| 6 | Limpeza final CODEX e homologação de encerramento | Quando o conjunto final estiver homologado, excluir somente contas CODEX registradas, revogar sessões e conferir evidências/fixtures. Não excluir administrador original ou contas reais. |

Fonte do requisito de plano da proteção de senhas:
[documentação Supabase](https://supabase.com/docs/guides/auth/password-security).

Domínio próprio e SMTP não são bloqueios atuais: o usuário escolheu manter o
domínio Railway e os convites funcionam por link. Produtos demo não devem virar
cadastros reais por efeito de sincronização. Não há porcentagem de conclusão
estimada: cada linha exige sua evidência específica.

## Próximo trabalho independente

Consolidar as ferramentas de recuperação e preparar o roteiro do ensaio integral
sem gravar no original. A transferência externa depende do destino; a gestão
Meta depende da credencial. Nunca pedir segredo pelo chat ou reutilizar a
conexão Make como se fosse automaticamente um token de administração do portal.

## Produto novo separado
VENDAXIS: cópia local preparada,145arquivosbaseline/5adaptaçõestécnicas/8testesisolamento/6SQLlocais; usuário decidiu não criar backend online agora. Não faz parte das pendências do VENDRA original. Ler COPIA_LOCAL_VENDAXIS_20261020.md.
