# H1-006I - Validação integrada e pendências

Estado observado em 15/10/2026, horário de Brasília. Este registro substitui o estado pendente da entrega H1-006H, preservada como histórico. Código de aplicação continua no commit e44d0bbdb360270385119edc41108c7375bd44ac; esta rodada alterou banco STAGING, configurações Make e documentação.

## Resultados funcionais

| Bloco | Evidência | Resultado e limite |
|---|---|---|
| Comando do portal | Formulário real, RPC, banco, Make e WhatsApp | Um template enviado; mesmo WAMID em disparo/mensagem/outbox; status automático até lido. |
| SQL09 | Migration vendra_dispatch_portal_request_v1 somente STAGING | ACL service_role, SECURITY INVOKER e search_path vazio conferidos. SQL10 de reversão não executado. |
| Concorrência do comando | Oito clientes SDK independentes | Um pedido criado e sete repetições reconhecidas; um conjunto cliente/atendimento/CRM/mensagem/disparo. Payload ou ator divergente rejeitado. |
| Gerencial | Transação real encerrada com ROLLBACK | Comando e reserva autorizados; nenhuma mudança permanente no perfil usado nem envio nesse teste. |
| Recuperação do portal | Túnel expirado antes da reserva | Renovação da ponte autorizada e reprocessamento do mesmo pedido; um único envio. Repetição posterior pelo serviço não chamou HTTP. |
| IA operacional | Entrada real, agente, callback67, WhatsApp75 e vínculo80 | Uma resposta enviada pelo REV9 original e lida; ramo #2 comprovado no cenário operacional. Outros ramos mantêm evidências separadas da cópia e dos contratos, sem alegar novo envio real de cada ramo. |
| Passagem para humano | RPC de modo + HTTP autenticado da ponte | Oito respostas tardias concorrentes rejeitadas por versão; resposta na versão atual também bloqueada em modo humano. Nenhuma outbox nova. Teste de controle pelo backend, ainda não do botão na interface operacional. |
| Portal Windows | Login HTTP real Comercial, cliente, atendimento, nota e CRM | Cadastro/edição/busca, movimento CRM, conflito409 sem retry, cliente inativo e CSRF aprovados. |
| Permissões | Perfil Comum existente com sessão temporária própria | Bloqueio403 em Clientes/Atendimentos/CRM/Disparos/Usuários. Comercial acessa os quatro primeiros e não gerencia usuários/funis. Isso testa autorização de sessões, sem alegar novo login por senha do Comum. |
| Reinício Windows | Reinício exclusivo da instância8011 | Sessão Comercial, cliente, nota e CRM preservados. Outras instâncias não reiniciadas. |

As 218 verificações automatizadas Windows da H1-006H continuam válidas para o código de aplicação inalterado; não foram executadas novamente nem somadas aos testes funcionais desta rodada.

## Mudanças externas e segurança operacional

Usuário autorizou SQL09 somente no VENDRA-STAGING e ajuste do Disparo Inicial6561096. Cenário agora reserva antes do template e confirma o WAMID depois, usando segredo próprio e destinatário de teste autorizado. SQL não habilitou worker, lote ou transporte automaticamente.

Usuário autorizou especificamente os callbacks65/67/69/79/80/81 no REV9 original6534261 após a revisão automática delimitar a autorização anterior a64/83. Alteração aplicada em15/10/2026 13:15:51 Brasília, com backup privado, configurações completas e mapeamentos do Watch Events nativo. Conteúdo usa base64 UTF8; vínculo exige token da reserva. Nenhuma mudança no banco ou na pasta do original.

Na recuperação do túnel8013 foram atualizados17HTTPs das integrações já apontadas para essa ponte, preservando demais campos. Isso não redirecionou8012 nem o túnel próprio do original. Túnel temporário continua sujeito a expiração; hospedagem precisará de domínio/serviço estável.

Duas tentativas IA anteriores não enviaram: a primeira foi bloqueada pela variante BR12/13dígitos; a segunda por texto recebido diferente do texto exato do filtro de teste. As reservas sem WAMID foram canceladas. Filtro final limitou atendimento exclusivo e ambas as formas equivalentes do destinatário; só a terceira entrada gerou transmissão. Não confundir essas reservas canceladas com três envios.

Estado final: três módulos de resposta do REV9 novamente bloqueados; template do Disparo Inicial bloqueado; transporte do portal desligado; worker desligado; flags temporárias removidas. Atendimento exclusivo IA encerrado em modo humano, preservando mensagens reais. Fixtures sintéticas CRUD/SQL e suas sessões próprias removidas. Contas CODEX permanecem até a homologação total. Banco/pasta principal não promovidos.

## Evidências verificáveis

- [Portal até envio e vínculo](https://us2.make.com/292724/scenarios/6561096/logs/842acc8e26924e5f9a80edbb9e80c7b9)
- [Status automático lido do template](https://us2.make.com/292724/scenarios/6534261/logs/8b37d27b3dab4479a0b4d3f1c813d6e2)
- [IA operacional com envio e vínculo](https://us2.make.com/292724/scenarios/6534261/logs/e2fdc62071554e96a22ed2c21727b66f)
- [Status automático lido da resposta IA](https://us2.make.com/292724/scenarios/6534261/logs/1aa6ba685a814db8bb7be2f3c9d6d1bc)
- [Portal local](http://127.0.0.1:8011/disparos/envio)

Relatórios privados resultado_portal_sql_h1006h.json e resultado_portal_blocos_h1006i.json, estado do teste IA, backups Make e screenshots permanecem fora do Git. Não publicar segredos, WAMIDs, sessões, credenciais ou payloads locais.

## O que ainda falta

1. Integrar a visualização do atendimento WhatsApp e a passagem humano/IA à interface que será promovida: a tela STAGING atual de Atendimentos é limitada a atendimento interno. Homologar o botão real com CSRF, permissões e controle persistente, sem substituir a evidência backend por um teste de tela simulado.
2. Conferir a composição de produção: remover dependências de fábricas/perfis exclusivos de STAGING da entrega aprovada e reconciliar migrations reais com o banco principal. Não promover tabelas staging_*, fixtures, sessões ou credenciais.
3. Ensaiar backup e restauração de banco em destino isolado e rollback do conjunto de promoção. O rollback de arquivos já testado não comprova restauração do banco.
4. Definir hospedagem e domínio estáveis; depois publicar e validar HTTPS, callback Meta/Make, persistência após reinício e o mesmo fluxo completo no ambiente hospedado. Ainda não existe servidor permanente confirmado.
5. Após aprovação do conjunto final, promoção seletiva com rastreabilidade e limpeza das contas CODEX. Não antecipar exclusão enquanto esses blocos dependem delas.

## Comandos

Nenhuma reinstalação manual necessária nesta sessão. Código já aplicado na cópia Windows. Para conferir o perfil padrão, sem iniciar outra instância:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.dispatch_portal_start --config .env.h1_005b2 --check
```

Regressão quando houver nova alteração de código:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

Atualizar apenas o clone de fontes, preservando alterações locais:

```powershell
$repo = 'C:\Users\israe\Downloads\Automações\VENDRA-GIT-STAGING'
git -C $repo fetch origin
if (git -C $repo status --porcelain) { throw 'Revisar alterações locais antes de atualizar' }
git -C $repo pull --ff-only
```

Startup8011 em uso nesta sessão usa perfil privado explícito com transporte desligado. Não iniciar outra instância sobre a mesma porta. Git sincroniza fontes/evidências; não equivale a hospedagem.
