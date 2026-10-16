"""Listas persistentes: selecao limitada, reserva atomica e fila sem reenvio cego."""
from __future__ import annotations
from pathlib import Path
from threading import Event,Thread
from uuid import UUID
import logging
from app.core.config import get_settings
from app.db.supabase import get_admin_client
from app.services import dispatch_command_service as command
from app.whatsapp_callbacks import canonical_phone

log=logging.getLogger(__name__)
def enabled():
    s=get_settings()
    if s.demo_mode or not getattr(s,'dispatch_lists_enabled',False):return False
    rows=get_admin_client().table('integration_settings').select('settings').eq('key','dispatch_lists').limit(1).execute().data or []
    return bool(rows and (rows[0].get('settings') or {}).get('enabled'))

def _require():
    if not enabled():raise ValueError('Importação e envio por lista estão desativados.')

def import_file(*,filename,content,imported_by):
    _require()
    from app.services.dispatch_import_service import parse_contact_file,_cell_text
    import re
    records,warnings=parse_contact_file(filename=filename,content=content)
    seen=set();items=[]
    for r in records:
        name=str(r.get('name') or '').strip()[:160];raw=_cell_text(r.get('phone_raw'))[:80]
        digits=re.sub(r'\D','',raw)
        if len(digits) in (10,11):digits='55'+digits
        try:phone=canonical_phone(digits)
        except ValueError:phone=''
        valid=bool(re.fullmatch(r'55[1-9][0-9][0-9]{8}',phone))
        status='ready';error=None
        if not name or not valid:status='invalid';error='Nome ausente ou telefone brasileiro inválido.'
        elif phone in seen:status='duplicate';error='Telefone repetido nesta lista.'
        else:seen.add(phone)
        items.append(dict(row_number=r['row_number'],name=name,phone_raw=raw,phone=phone if valid else None,status=status,last_error=error))
    return get_admin_client().rpc('vendra_dispatch_list_import_v1',dict(p_actor_id=str(UUID(str(imported_by))),p_filename=Path(filename).name,p_extension=Path(filename).suffix.lower(),p_records=items,p_warnings=warnings)).execute().data

def batches(limit=30):
    if not enabled():return []
    return get_admin_client().table('dispatch_import_batches').select('*').order('created_at',desc=True).limit(min(max(limit,1),100)).execute().data or []

def batch(batch_id):
    if not batch_id or not enabled():return None
    try:batch_id=str(UUID(str(batch_id)))
    except ValueError:return None
    rows=get_admin_client().table('dispatch_import_batches').select('*').eq('id',batch_id).limit(1).execute().data or []
    return rows[0] if rows else None

def items(batch_id):
    if not enabled():return []
    # Data API normalmente limita1000: paginar explicitamente a lista completa.
    db=get_admin_client();rows=[]
    for offset in range(0,20000,500):
        part=db.table('dispatch_import_items').select('*').eq('batch_id',batch_id).order('row_number').range(offset,offset+499).execute().data or []
        rows.extend(part)
        if len(part)<500:break
    linked={r['dispatch_id'] for r in rows if r.get('dispatch_id')};dispatches={}
    ids=list(linked)
    for offset in range(0,len(ids),200):
        for d in db.table('dispatches').select('id,status,last_error').in_('id',ids[offset:offset+200]).execute().data or []:dispatches[d['id']]=d
    from app.services.dispatch_import_service import _status_label
    for r in rows:
        if r.get('dispatch_id') in dispatches:
            d=dispatches[r['dispatch_id']]
            status=r['status'] if r['status']=='processing' and d['status']=='pending' else d['status']
            r.update(status=status,last_error=d.get('last_error') or r.get('last_error'))
        r['status_label']=_status_label(r['status'])
    return rows

def state(batch_id):
    b=batch(batch_id)
    if not b:raise ValueError('Lista importada não encontrada.')
    rows=items(batch_id);selected=[r for r in rows if r.get('queued_at') or r.get('dispatch_id')]
    pending=sum(r['status'] in ('queued','processing') for r in selected)
    failed=sum(r['status'] in ('failed','cancelled') for r in selected)
    processed=sum(r['status'] not in ('queued','processing') for r in selected)
    total=len(selected);status=b['bulk_status']
    if status in ('queued','running') and not pending:
        status='completed_with_errors' if failed else 'completed'
        get_admin_client().table('dispatch_import_batches').update({'bulk_status':status}).eq('id',batch_id).in_('bulk_status',['queued','running']).execute()
    return dict(status=status,total=total,processed=processed,failed=failed,remaining=pending,percent=round(processed/total*100) if total else 0)

def start(*,batch_id,requested_by,quantity=None):
    _require()
    if not command.channel_ready():raise ValueError('O envio deste canal está desativado.')
    ready=sum(r['status']=='ready' for r in items(batch_id))
    quantity=ready if quantity is None else quantity
    if quantity<1 or quantity>ready:raise ValueError('Informe uma quantidade entre 1 e o total de contatos prontos.')
    get_admin_client().rpc('vendra_dispatch_list_start_v1',dict(p_actor_id=requested_by,p_batch_id=batch_id,p_quantity=quantity)).execute()
    return state(batch_id)

def _finish(result):
    row=result['dispatch'];item_id=result['item_id']
    try:
        sent=command.transmit_dispatch(row)
        status=sent.get('status','pending')
        if status=='pending':status='submitted' if sent.get('transport_confirmed') else 'pending'
        error=None if sent.get('transport_confirmed') else 'Confirmação pendente; conferir histórico antes de repetir.'
    except Exception:
        # Reserva existe: conservar IDs, sem repetir automaticamente o transporte.
        status='pending';error='Pedido reservado; confirmação pendente. Consulte o histórico.'
    get_admin_client().table('dispatch_import_items').update({'status':status,'last_error':error}).eq('id',item_id).eq('status','processing').execute()
    return {'item':{'id':item_id},'dispatch':{**row,'status':status},'already_requested':row.get('status')!='pending'}

def send_item(*,item_id,requested_by,batch_id):
    _require()
    if not command.channel_ready():raise ValueError('O envio deste canal está desativado.')
    _,stage=command._new_lead_destination()
    result=get_admin_client().rpc('vendra_dispatch_list_item_v1',dict(p_actor_id=requested_by,p_batch_id=batch_id,p_item_id=item_id,p_stage_id=stage)).execute().data
    return _finish(result)

def process_one():
    # Na fila vazia, uma consulta leve; nao recarregar funis/configuracoes a cada segundo.
    if not getattr(get_settings(),'dispatch_lists_enabled',False):return False
    queued=get_admin_client().table('dispatch_import_items').select('id').eq('status','queued').limit(1).execute().data or []
    if not queued:return False
    if not enabled() or not command.channel_ready():return False
    _,stage=command._new_lead_destination()
    result=get_admin_client().rpc('vendra_dispatch_list_claim_v1',{'p_stage_id':stage}).execute().data
    if not result.get('claimed'):return False
    _finish(result);state(result['batch_id']);return True

def start_worker():
    """Uma mensagem por segundo no maximo; fila/IDs ficam no banco, nao em RAM."""
    stop=Event()
    if not getattr(get_settings(),'dispatch_lists_enabled',False):return stop,None
    def run():
        while not stop.is_set():
            worked=False
            try:worked=process_one()
            except Exception as exc:log.warning('dispatch_list_worker: %s',type(exc).__name__)
            stop.wait(1 if worked else 15)
    thread=Thread(target=run,name='vendra-dispatch-list',daemon=True);thread.start();return stop,thread
