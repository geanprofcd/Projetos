# H1-006M - Composer humano e anexos no STAGING

Validação em 15/10/2026, na cópia Windows local8014 e no Supabase VENDRA-STAGING. Original, seu banco e design preservados; sem hospedagem ou envio WhatsApp nesta rodada.

## Correções aplicadas na cópia

O formulário comercial agora inclui um token CSRF invisível, validado antes de leitura/escrita. A comparação com o template original confirmou que essa linha é a única diferença do HTML: nenhum layout, elemento visível, CSS, JS ou navegação foi alterado. A pasta original não recebeu arquivos.

Resposta humana WhatsApp passa a exigir confirmação do handoff antes de gravar mensagem, anexo ou outbox. Antes, a falha do controle era ignorada e o fluxo continuava; agora retorna422 e preserva o texto digitado. A camada persistente sob flag registra corretamente canal WhatsApp e autoria humana; notas internas continuam internas.

O STAGING não tinha bucket de anexos. Foi criado `ticket-attachments`, privado, limite50MiB, exclusivamente nesse projeto, sem conceder acesso público ou alterar RLS. O limite de cada tipo de arquivo continua validado também pelo backend. O original não foi provisionado nesta etapa.

## Evidências aprovadas

- **258 testes Windows passaram em2,949s**, em snapshot limpo/UTF8: `VENDRA-validacoes/staging_20261015_230826_625_cf7397d5/resultado.json`. Nove novos casos exercitam CSRF, handoff antes da persistência, falha fechada, arquivo inválido, limite de seis anexos, janela expirada, nota interna, metadados humanos e rollback técnico em falha simulada do segundo upload. O traceback `storage unavailable` no log é esperado desse teste de falha; suíte terminou OK/código0.
- **22 verificações funcionais reais HTTP/SDK/banco/Storage** na rodada concluída: login Comercial; campo CSRF invisível; CSRF ausente/incorreto sem escrita; mensagem vazia; executável; sete anexos; texto/anexo persistidos; handoff com ator Comercial; canal/autoria humanos; uma outbox pending sem WAMID; checksum/tamanho do anexo; escape do texto; download autorizado por URL assinada; bytes reais iguais; acesso público ao bucket negado; download anônimo redirecionado ao login; anexo em outro atendimento404; nota interna sem nova outbox; janela expirada422 sem escrita; atendimento encerrado/handoff recusado422 sem escrita; ausência de envio real.
- Foi usada uma entrada **sintética**, identificada como fixture, para abrir a janela do atendimento de teste. Não é evidência de recepção real do Meta. Recepção e IA reais anteriores permanecem documentadas em H1-006I.
- Duas tentativas anteriores não foram contadas como homologação completa: source `internal` inválido da fixture foi corrigido para `portal`; depois, um GET da tela falhou por ReadError WinError10035 do Supabase. Ambas tiveram limpeza automática. Rodada final manteve todas as assertions e aprovou os22casos. O auxiliar permite no máximo uma releitura de GET em5xx, registra a ocorrência e nunca repete POST/envio; não altera as verificações. Verificar logs de conectividade caso reapareça.
- Fixtures próprias: dois atendimentos, mensagens sintéticas, anexo e objeto Storage, outbox pendente e sessões criadas pela rodada foram removidos. Exclusão restrita a IDs/títulos/prefixos registrados pelo próprio teste. Evidências reais de WhatsApp, cliente existente e contas CODEX preservados. Bucket privado permanece como configuração funcional do STAGING.

O navegador passou a apresentar timeouts de conexão CDP após o clique H1-006L. A rodada M foi validada por endpoints comerciais reais, HTML e bytes de Storage, sem alegar clique ou screenshot novo no navegador. A comparação do template, descontando apenas o input oculto, confirmou layout inalterado. Não confundir isso com uma nova homologação visual de todos os estados interativos.

## Limites e próximos blocos

Esta rodada homologa persistência e anexos privados no STAGING, com saída enfileirada e não transmitida. **Não homologa envio humano até o WhatsApp, envio de mídia ao provedor, idempotência de duplo clique do composer nem recuperação completa após falha de rede de uma escrita.** O handoff ocorre antes da gravação, mas a sequência mensagem/anexo/outbox ainda não é uma única transação de banco. A reversão técnica foi exercitada com falha simulada; não declarar atomicidade total.

Continuar o levantamento do fluxo humano no Make e a integração comercial de Disparos/importação/lote, além do padrão IA de novos atendimentos. Não habilitar worker/lote/envio como efeito de instalar código. Depois ensaiar backup/restauração e promoção seletiva, preservando design, estado e configurações do original. Só então publicar o original finalizado e validar callbacks/HTTPS/reinício no servidor. STAGING online somente se indispensável.

## Comandos

Código já aplicado na cópia local, prévia8014 reiniciada. Não é necessária reinstalação nesta sessão.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.commercial_preview_start --config .env.h1_005b2 --check
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

Primeiro apenas confere perfil. Prévia ativa usa perfil privado explícito com controle persistente true e transporte false; perfil base preservado. Não duplicar processo na8014. Nenhum SQL adicional foi aplicado na rodada M. Provisionar Storage no original será uma etapa separada, após reconciliação da configuração já existente, sem copiar objetos de teste.

[Controle da equipe e configuração global](VALIDACAO_EQUIPE_GLOBAL_H1_006L.md) | [Estado atual](VALIDACAO_ATUAL.md)
