# Custos estimados do VENDRA - 16/10/2026

Orcamento mensal de planejamento, nao fatura nem promessa de capacidade. Nenhum plano foi contratado ou compra realizada.

Cambio hipotetico: US$1 = R$5.50; nao e cotacao de hoje. Meta em BRL: marketing0,3217/mensagem entregue; servico0,035 apos franquia mensal de1000 por numero. Se a WABA for faturada em USD, usar0,0625/marketing e0,0068/servico, convertidos pelo cambio efetivo. Moeda de faturamento da conta ainda nao confirmada.

Template continuar_atendimento_vendra confirmado marketing/billable/regular pelo webhook real da Meta. N considera mensagens entregues a numeros brasileiros; falhas tambem podem consumir Make mesmo sem cobranca Meta. Nao ha desconto marketing por volume incluido.

Infraestrutura: reserva RailwayUS$10/mes (minimo HobbyUS$5, consumo pode exceder) + Supabase ProUS$25/mes para um projeto Micro. Supabase Free, se mantido e dentro das cotas, reduz R$137.50 por mes. Segundo projeto pago pode acrescentar compute. Nao foi confirmado o plano atual da organizacao; esta e uma configuracao de referencia.

Make: reserva de orcamento, nao cotacao contratual:10kUS$12;20kUS$21;40kUS$40;80kUS$75;150kUS$130;300kUS$240;750kProUS$750. Valores arredondados para cima; cotacoes publicas UI consultadas:10kCore10,59;20k18,82;40k34,12;80k64,71;150k116,47;300k214,31;750kPro678,75. Preco final depende da conta/moeda/periodo; nao multiplicar somente os5modulos de envio e ignorar callbacks.

Base Make:11creditos/disparo (5observados+3statusx2). Teste real teve5creditos+2callbacksx2=9ateentregue;11inclui eventualleitura. Repeticoes, erros e outros cenarios nao incluidos. Modelo com IA:20%respondemx5respostas=1resposta por disparo em media;15creditos adicionais por resposta,8mil tokensentrada+500saida, GPT6Luna0,10/1Mentrada+0,50/1Msaida sem desconto de cache. Ferramentas/retrieval/arquivos extras e contextos maiores podem acrescer custo. A contagem de tokens nao foi medida nesta simulacao.

| Disparos/mes | Meta (R$) | Make reservado (US$) | Total so disparos (R$) | Total com cenario IA (R$) |
|---:|---:|---:|---:|---:|
| 1 | 0.32 | 12.00 | 258.82 | 258.83 |
| 100 | 32.17 | 12.00 | 290.67 | 291.25 |
| 1000 | 321.70 | 21.00 | 629.70 | 739.98 |
| 5000 | 1608.50 | 75.00 | 2213.50 | 2684.88 |
| 10000 | 3217.00 | 130.00 | 4124.50 | 5102.25 |
| 20000 | 6434.00 | 240.00 | 7946.50 | 11532.00 |

Totais incluem infraestrutura e o plano Make inteiro escolhido, nao apenas custo marginal; se ja existe assinatura com creditos livres, o incremento pode ser menor. Nao incluem impostos/IOF/spread, anuncios, dominio, operacao humana, suporte, armazenamento adicional ou custo de desenvolvimento. Adotar margem operacional antes de definir preco comercial.

Fontes primarias consultadas:
https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing
https://www.make.com/pricing
https://help.make.com/credits
https://developers.openai.com/api/docs/models/gpt-6-luna
https://railway.com/pricing
https://supabase.com/pricing

Recalcular sem acessar provedores:
```powershell
python -X utf8 tools/calcular_custos_vendra.py --cambio 5.50
```

Volume projetado nao significa carga20mil homologada nem autoriza envio20mil. Disparo individual validado e liberacao regular autorizada; listas persistentes/quantidade em desenvolvimento STAGING. Sem disparar mensagens por efeito desta simulacao.
