"""CRUD de Clientes H1-005B2 limitado ao STAGING e protegido com CSRF."""
from __future__ import annotations
from fastapi import APIRouter,Depends,Form,HTTPException,Request
from fastapi.responses import RedirectResponse
from app.core.ui import templates
from app.dependencies.auth import current_user
from app.services.access_service import require_access
from app.services.auth_service import COOKIE_NAME, csrf_token_for_session, verify_csrf_token
from app.services.customer_service import list_customers,get_customer,create_customer,update_customer
from app.services.audit_service import record_audit

router=APIRouter(prefix='/clientes',tags=['staging-clientes'])

def _auth(u):return require_access(u,'clientes')
def _csrf(request,code):
    if not verify_csrf_token(request.cookies.get(COOKIE_NAME),code):
        raise HTTPException(status_code=403,detail='Formulario expirado/invalido. Recarregue a pagina.')
def _ctx(request,u,customer=None,error=None):
    return {'user':u,'customer':customer,'error':error,'active_page':'customers',
            'csrf_token':csrf_token_for_session(request.cookies.get(COOKIE_NAME))}

@router.get('')
def listing(request:Request,q:str|None=None,user:dict=Depends(current_user)):
    _auth(user)
    return templates.TemplateResponse(request=request,name='customers/list.html',
        context={'user':user,'customers':list_customers(q),'query':q or '', 'active_page':'customers'})

@router.get('/novo')
def new_page(request:Request,user:dict=Depends(current_user)):
    _auth(user)
    return templates.TemplateResponse(request=request,name='customers/form.html',context=_ctx(request,user))

@router.post('/novo')
def new(request:Request,name:str=Form(...),phone:str=Form(''),email:str=Form(''),document:str=Form(''),
        company_name:str=Form(''),csrf_token:str=Form(''),user:dict=Depends(current_user)):
    _auth(user);_csrf(request,csrf_token)
    try:
        c=create_customer(name=name,phone=phone,email=email,document=document,company_name=company_name)
        record_audit(actor_id=user.get('id'),entity_type='customer',entity_id=c['id'],action='created',payload={'name':c['name']})
    except ValueError as exc:
        return templates.TemplateResponse(request=request,name='customers/form.html',status_code=422,
           context=_ctx(request,user,{'name':name,'phone':phone,'email':email,'document':document,'company_name':company_name},str(exc)))
    return RedirectResponse('/clientes/'+str(c['id']),status_code=303)

@router.get('/{customer_id}')
def detail(customer_id:str,request:Request,user:dict=Depends(current_user)):
    _auth(user)
    c=get_customer(customer_id)
    if not c:raise HTTPException(404,'Cliente nao encontrado.')
    return templates.TemplateResponse(request=request,name='customers/detail.html',
        context={'user':user,'customer':c,'tickets':[],'opportunities':[],'active_page':'customers'})

@router.get('/{customer_id}/editar')
def edit_page(customer_id:str,request:Request,user:dict=Depends(current_user)):
    _auth(user)
    c=get_customer(customer_id)
    if not c:raise HTTPException(404,'Cliente nao encontrado.')
    return templates.TemplateResponse(request=request,name='customers/form.html',context=_ctx(request,user,c))

@router.post('/{customer_id}/editar')
def edit(customer_id:str,request:Request,name:str=Form(...),phone:str=Form(''),email:str=Form(''),document:str=Form(''),
         company_name:str=Form(''),status:str=Form('active'),csrf_token:str=Form(''),user:dict=Depends(current_user)):
    _auth(user);_csrf(request,csrf_token)
    try:
        c=update_customer(customer_id,name=name,phone=phone,email=email,document=document,company_name=company_name,status=status)
        record_audit(actor_id=user.get('id'),entity_type='customer',entity_id=customer_id,action='updated',payload={'status':c['status']})
    except ValueError as exc:
        return templates.TemplateResponse(request=request,name='customers/form.html',status_code=422,
            context=_ctx(request,user,{'id':customer_id,'name':name,'phone':phone,'email':email,'document':document,
                'company_name':company_name,'status':status},str(exc)))
    return RedirectResponse('/clientes/'+customer_id,status_code=303)
