# Alerta de atraso: última mensagem do lead

16/10/2026. O alerta começa ao completar 30 minutos da última mensagem externa recebida do lead, enquanto não existir uma resposta externa posterior enviada por humano ou IA. Uma nova mensagem do lead reinicia a contagem. Atendimento finalizado/cancelado não alerta.

Foi encontrada e corrigida uma falha no serviço: `claimed` era considerado resposta, embora seja apenas a reserva anterior ao envio no Make. Agora `pending`, `claimed`, `failed`, `cancelled` e notas internas não encerram a espera. `sent`, `delivered` e `read` encerram, independentemente de humano/IA. Mensagens internas legadas sem status continuam compatíveis; nenhuma migration ou alteração de Make é necessária.

## Evidência

- 14 testes automatizados passaram: dez testes de SLA, com subcasos humano/IA/status, e quatro de ordenação existente. Limites exatos 29:59/30:00, última entrada, nova entrada após resposta, fechamento, notas internas e reservas/falhas cobertos.
- 12 verificações HTTP com banco STAGING real pela rota `/atendimentos/alertas.json`, login Comercial, dados temporários exclusivos CODEX: 29/31 minutos, nova entrada, resposta humana, resposta IA, nota interna, quatro estados não enviados, novo atraso após resposta e finalização. Fixtures removidas; nenhuma outbox criada e nenhum WhatsApp enviado.
- A interface já consulta a rota a cada 15 segundos enquanto a página está visível. No próximo polling bem-sucedido, retira da lista e do destaque os atrasos respondidos. O relógio usa o instante persistido da mensagem; não depende de esperar 30 minutos de teste em tempo real.

## Aplicação e reversão

Somente `app/services/ticket_attention_service.py` alterado no backend original Windows e na release privada Railway. `.env`, `app/main.py` e `app/templates/base.html` preservados por hash; nenhum template/CSS alterado. Backup: `output/backups/alertas-original-20261016/app/services/ticket_attention_service.py`, com manifesto de hashes. SQL, permissões, IA, campanhas e configurações existentes preservados.

Deploy `c70381a4-4139-4d33-abb1-238084f840de` concluído com SUCCESS. Login Comercial e rota online retornaram 303/200; limite 30 e Cache-Control no-store confirmados. A conversa real de Calendly, cuja saída posterior está read no banco original, ficou fora dos alertas. Kanban e feed retornaram 200, cinco colunas; acesso Comercial à administração permaneceu 403. Logs observados sem traceback/erro da aplicação após o deploy. Não houve novo envio nem alteração de Make. Reversão exige restaurar somente o serviço do backup e republicar a release limpa, ou selecionar o deployment anterior `797c35cf-6a1b-4237-ad3b-f4035bb36b99`. Não executar rollback SQL.

Comando para repetir os testes locais na cópia, sem enviar mensagens:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_ticket_attention tests.test_conversation_order
```

O original já recebe a correção pela publicação; o usuário não precisa executar comandos de atualização. Pacote Windows separado contém os arquivos selecionados, hashes, instalador com backup e instruções. Este pacote não contém credenciais, dados de clientes ou SQL.
