# H1-006K - Backend persistente no layout comercial existente

Validação em 15/10/2026, somente na cópia Windows e no Supabase STAGING. O original permaneceu intocado; nenhum STAGING foi hospedado. A prévia comercial local 8014 usa `app.main`, o router de Atendimentos e o template comercial existentes, com perfil privado explícito e sem transporte de disparos.

## Mudanças e evidências

O controle comercial real antes retornava sempre humano/requires_migration, e as respostas IA eram renderizadas como se tivessem autoria do cliente, porque `sender_kind` não era selecionado. A nova opção `WHATSAPP_PERSISTENT_CONTROL_ENABLED`, desligada por padrão, liga o adaptador às RPCs já homologadas de leitura e troca de modo. A autoria IA e a confirmação Lido passam a usar os componentes comerciais já existentes. Nenhum template, CSS, JS, main ou router comercial foi modificado nesta etapa.

- **248 testes Windows aprovados em 2,532 s**, em cópia limpa, incluindo 13 novos testes do adaptador/contrato/autoria. Relatório privado: VENDRA-validacoes/staging_20261015_222136_889_1f825fa0/resultado.json.
- **Seis verificações funcionais reais** no layout comercial: Desconectar IA -> banco humano; Reconectar IA -> banco ai; Desconectar IA -> humano final; feed identifica única resposta IA/read; controle lê versão persistida; nenhuma outbox/envio novo.
- Dados reais da H1-006I reutilizados. Conta CODEX administrativa autorizada foi reativada apenas para este teste, depois novamente inativada/sessões revogadas. Atendimento exclusivo restaurado ao estado encerrado e responsável anterior; flag temporária removida. Nenhum usuário novo ou mensagem enviada nesta rodada.
- Integridade conferida: main, router comercial e template de atendimento da cópia continuam idênticos aos da pasta original. Relatório privado original_ui_integrity_h1006k.json. O design não foi substituído pela tela `/conversas` do protótipo.

O adaptador valida ator real e perfil ativo, usa comparação atômica de versão e não repete a escrita em conflito. Não impersona administrador nem amplia permissões SQL. A reconexão exige automação global disponível e janela de 24 h aberta; desconexão continua disponível quando a janela fecha. A flag desligada preserva o caminho anterior; nenhuma ativação implícita por instalar o pacote.

## Limites que impedem declarar o original pronto

1. As RPCs atuais autorizam troca persistente de modo somente para administrador. A interface comercial antiga permite entrada da equipe aos controles, mas não foi concedida permissão persistente adicional a Comercial/Gerencial. Alinhar essa política explicitamente antes da promoção; não mascarar a limitação nem usar ator administrativo em nome da equipe.
2. A configuração comercial global usa `ai_automation`; os testes atuais usam `whatsapp_bridge` como flag controlada. A composição final precisa reconciliar esse contrato e validar o padrão de IA no novo atendimento. Esta rodada não homologou salvar a configuração global pela tela comercial.
3. Na camada comercial original, `dispatch_service` e `dispatch_import_service` ainda contêm bloqueios para disparo/importação/lote no Supabase real. O comando individual da tela STAGING foi aprovado, mas isso não homologa automaticamente esses caminhos comerciais. Adaptar seus backends mantendo o design e sem habilitar lote/worker como efeito de instalar código.
4. Mensagem humana pelo composer, anexos e demais fluxos afetados devem compor a homologação comercial final. Não extrapolar o teste dos botões IA para afirmar todo o produto aprovado.
5. Depois reconciliar migrations/configurações próprias, ensaiar backup/restauração e rollback e promover somente o conjunto homologado. Publicar o original finalizado no Railway e então validar HTTPS/callbacks/reinício. STAGING online apenas se um teste indispensável exigir.

Essas são pendências identificadas no levantamento; testes offline, protótipos e projeto Railway vazio não as encerram. Não promover factories, tabelas staging_*, credenciais, dados ou templates de teste ao original.

## Comandos

Prévia comercial local da cópia (não executar na pasta original):

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tools.commercial_preview_start --config .env.h1_005b2 --check
.\.venv\Scripts\python.exe -X utf8 -m tools.commercial_preview_start --config .env.h1_005b2
```

Primeiro comando somente confere perfil; segundo inicia localhost:8014. Não duplicar o processo enquanto a porta estiver em uso. O perfil padrão mantém a flag persistente desligada; a instância desta sessão usa perfil privado exclusivo, com a flag ativada e transporte desligado. Nenhum segredo é necessário no repositório.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validar_staging.ps1
```

Regressão completa, com UTF8, snapshot e hashes. Original não atualizado, nenhum banco principal alterado, nenhum serviço Railway criado.

- [Validação da integração anterior](VALIDACAO_INTEGRADA_H1_006I.md)
- [Protótipo STAGING, não promover ao produto](VALIDACAO_CONVERSAS_STAGING_H1_006J.md)
- [Prévia comercial local de testes](http://127.0.0.1:8014/atendimentos)


Estado histórico K: SQL11 e rollback12 estavam preparados, não executados. Atualização H1-006L: após autorização específica, SQL11 aplicado somente no STAGING e backend da cópia alinhado; SQL12 não executado. Ler [validação H1-006L](VALIDACAO_EQUIPE_GLOBAL_H1_006L.md). Instalar arquivos não executa SQL ou altera permissões do banco original.

