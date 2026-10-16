"""Orcamento reproduzivel; nao acessa provedores nem dispara mensagens."""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import argparse,json

def calculate(n,fx):
    # Reservas de orcamento arredondadas acima das cotacoes publicas consultadas.
    plans=[(10000,12),(20000,21),(40000,40),(80000,75),(150000,130),(300000,240),(750000,750)]
    def make_budget(credits):
        return next((Decimal(price),capacity) for capacity,price in plans if capacity>=credits)
    initial=Decimal(n)*Decimal('0.3217')
    # Cinco modulos no envio observado + ate tres callbacks de dois creditos.
    credits=n*11
    mb,capacity=make_budget(credits)
    infrastructure=Decimal(35)*fx # Railway reserva10 + Supabase Pro25/um projeto.
    initial_total=initial+mb*fx+infrastructure
    # Cenario:20%respondem e cada um recebe5respostas => N respostas no total.
    replies=n
    ai=Decimal(replies)*Decimal('0.00105')*fx # 8k entrada+500saida GPT6Luna, semcache.
    service=Decimal(max(replies-1000,0))*Decimal('0.035')
    reply_credits=credits+15*replies
    reply_mb,reply_capacity=make_budget(reply_credits)
    conversation_total=initial+service+ai+reply_mb*fx+infrastructure
    money=lambda v:str(v.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))
    return dict(disp= n,meta_brl=money(initial),make_credits=credits,make_capacity=capacity,
        make_budget_usd=money(mb),infrastructure_brl=money(infrastructure),initial_total_brl=money(initial_total),
        replies=replies,ai_brl=money(ai),service_brl=money(service),conversation_credits=reply_credits,
        conversation_make_capacity=reply_capacity,conversation_make_usd=money(reply_mb),conversation_total_brl=money(conversation_total))

def main():
    p=argparse.ArgumentParser();p.add_argument('--cambio',default='5.50');args=p.parse_args();fx=Decimal(args.cambio)
    assert fx>0
    rows=[calculate(n,fx) for n in [1,100,1000,5000,10000,20000]]
    root=Path(__file__).resolve().parents[1]
    out=root/'output/custos';out.mkdir(parents=True,exist_ok=True)
    (out/'simulacao_20261016.json').write_text(json.dumps({'date':'2026-10-16','fx_assumption':str(fx),'rows':rows},indent=2),encoding='utf8')
    lines=['# Custos estimados do VENDRA - 16/10/2026','',
      'Orcamento mensal de planejamento, nao fatura nem promessa de capacidade. Nenhum plano foi contratado ou compra realizada.', '',
      f'Cambio hipotetico: US$1 = R${fx}; nao e cotacao de hoje. Meta em BRL: marketing0,3217/mensagem entregue; servico0,035 apos franquia mensal de1000 por numero. Se a WABA for faturada em USD, usar0,0625/marketing e0,0068/servico, convertidos pelo cambio efetivo. Moeda de faturamento da conta ainda nao confirmada.', '',
      'Template continuar_atendimento_vendra confirmado marketing/billable/regular pelo webhook real da Meta. N considera mensagens entregues a numeros brasileiros; falhas tambem podem consumir Make mesmo sem cobranca Meta. Nao ha desconto marketing por volume incluido.', '',
      'Infraestrutura: reserva RailwayUS$10/mes (minimo HobbyUS$5, consumo pode exceder) + Supabase ProUS$25/mes para um projeto Micro. Supabase Free, se mantido e dentro das cotas, reduz R$'+str(25*fx)+' por mes. Segundo projeto pago pode acrescentar compute. Nao foi confirmado o plano atual da organizacao; esta e uma configuracao de referencia.', '',
      'Make: reserva de orcamento, nao cotacao contratual:10kUS$12;20kUS$21;40kUS$40;80kUS$75;150kUS$130;300kUS$240;750kProUS$750. Valores arredondados para cima; cotacoes publicas UI consultadas:10kCore10,59;20k18,82;40k34,12;80k64,71;150k116,47;300k214,31;750kPro678,75. Preco final depende da conta/moeda/periodo; nao multiplicar somente os5modulos de envio e ignorar callbacks.', '',
      'Base Make:11creditos/disparo (5observados+3statusx2). Teste real teve5creditos+2callbacksx2=9ateentregue;11inclui eventualleitura. Repeticoes, erros e outros cenarios nao incluidos. Modelo com IA:20%respondemx5respostas=1resposta por disparo em media;15creditos adicionais por resposta,8mil tokensentrada+500saida, GPT6Luna0,10/1Mentrada+0,50/1Msaida sem desconto de cache. Ferramentas/retrieval/arquivos extras e contextos maiores podem acrescer custo. A contagem de tokens nao foi medida nesta simulacao.', '',
      '| Disparos/mes | Meta (R$) | Make reservado (US$) | Total so disparos (R$) | Total com cenario IA (R$) |',
      '|---:|---:|---:|---:|---:|']
    for r in rows:lines.append(f"| {r['disp']} | {r['meta_brl']} | {r['make_budget_usd']} | {r['initial_total_brl']} | {r['conversation_total_brl']} |")
    lines+=['','Totais incluem infraestrutura e o plano Make inteiro escolhido, nao apenas custo marginal; se ja existe assinatura com creditos livres, o incremento pode ser menor. Nao incluem impostos/IOF/spread, anuncios, dominio, operacao humana, suporte, armazenamento adicional ou custo de desenvolvimento. Adotar margem operacional antes de definir preco comercial.', '',
      'Fontes primarias consultadas:','https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing',
      'https://www.make.com/pricing','https://help.make.com/credits','https://developers.openai.com/api/docs/models/gpt-6-luna',
      'https://railway.com/pricing','https://supabase.com/pricing','',
      'Recalcular sem acessar provedores:','```powershell','python -X utf8 tools/calcular_custos_vendra.py --cambio 5.50','```','',
      'Volume projetado nao significa carga20mil homologada nem autoriza envio20mil. Disparo individual validado e liberacao regular autorizada; listas persistentes/quantidade em desenvolvimento STAGING. Sem disparar mensagens por efeito desta simulacao.']
    (root/'docs/CUSTOS_VENDRA_20261016.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps(rows,ensure_ascii=False))
if __name__=='__main__':main()

