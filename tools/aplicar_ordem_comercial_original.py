"""Atualiza somente duas funcoes de consulta, preservando o restante do original."""
from pathlib import Path
import argparse,ast,shutil,hashlib


REPLACEMENTS={
 'list_tickets': '''def list_tickets(user: dict, limit: int = 100) -> list[dict]:
    from app.services.conversation_order_service import list_ticket_rows
    customer_ids = _customer_ids_for_user(user) if user.get('role')=='agronomo' else None
    if customer_ids == []:
        return []
    return _enrich(list_ticket_rows(customer_ids=customer_ids,limit=limit))''',
 'list_tickets_for_customer': '''def list_tickets_for_customer(customer_id: str, user: dict, limit: int = 30) -> list[dict]:
    if user.get('role') == 'agronomo' and customer_id not in set(_customer_ids_for_user(user)):
        return []
    from app.services.conversation_order_service import list_ticket_rows
    return _enrich(list_ticket_rows(customer_ids=[customer_id],limit=limit))''',
}


def transform(text):
    nodes=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name in REPLACEMENTS]
    if {n.name for n in nodes}!=set(REPLACEMENTS):raise ValueError('Funcoes esperadas ausentes')
    lines=text.splitlines(keepends=True)
    for n in sorted(nodes,key=lambda n:n.lineno,reverse=True):
        lines[n.lineno-1:n.end_lineno]=[REPLACEMENTS[n.name]+'\n']
    result=''.join(lines);ast.parse(result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--target',type=Path,required=True);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    target=args.target.resolve()
    if target.name!='ticket_service.py' or target.parent.name!='services':raise ValueError('Destino inesperado')
    original=target.read_text(encoding='utf8');updated=transform(original)
    if args.apply and updated!=original:
        backup=target.with_name(target.name+'.antes_ordem_comercial.bak')
        if not backup.exists():shutil.copy2(target,backup)
        target.write_text(updated,encoding='utf8')
    print({'changed':updated!=original,'applied':args.apply,'sha256':hashlib.sha256(updated.encode()).hexdigest()})
