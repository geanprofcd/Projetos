"""Permissões por módulo; compatível com papéis legados do Plantar/VENDRA.

`access_level` passa a ser a fonte de verdade; `role` continua sendo campo legado
para funções operacionais que ainda esperam `responsavel` / `administrador`.
"""
from __future__ import annotations

from fastapi import HTTPException

LEVELS = ('comum', 'comercial', 'gerencial', 'administrativo')
LABELS = {'comum': 'Comum', 'comercial': 'Comercial', 'gerencial': 'Gerencial', 'administrativo': 'Administrativo'}
MODULES = {
    'comum': frozenset(),
    'comercial': frozenset({'atendimentos', 'clientes', 'produtos', 'disparos', 'oportunidades'}),
    'gerencial': frozenset({'atendimentos', 'clientes', 'produtos', 'disparos', 'oportunidades', 'indicadores'}),
    'administrativo': frozenset({'atendimentos', 'clientes', 'produtos', 'disparos', 'oportunidades', 'indicadores', 'configuracoes', 'integracoes', 'auditoria', 'usuarios'}),
}


def level_for(user: dict | None) -> str:
    if not user:
        return 'comum'
    value = str(user.get('access_level') or '').strip().lower()
    if value in LEVELS:
        return value
    # Contas antigas sem coluna migrada conservam sua permissão anterior.
    return {'administrador': 'administrativo', 'responsavel': 'comercial', 'agronomo': 'comum'}.get(user.get('role'), 'comum')


def allowed(user: dict | None, module: str) -> bool:
    return (module in MODULES[level_for(user)]) or (module == "usuarios" and bool((user or {}).get("can_manage_users")))


def require_access(user: dict, module: str) -> dict:
    if not allowed(user, module):
        raise HTTPException(status_code=403, detail='Seu perfil não tem permissão para esta área.')
    return user


def module_for_path(path: str) -> str | None:
    if path.startswith('/atendimentos'):return 'atendimentos'
    if path.startswith('/clientes'):return 'clientes'
    if path.startswith('/produtos'):return 'produtos'
    if path.startswith('/disparos'):return 'disparos'
    if path.startswith('/oportunidades'):return 'oportunidades'
    if path.startswith('/indicadores'):return 'indicadores'
    if path.startswith('/configuracoes'):return 'configuracoes'
    if path.startswith('/integracoes'):return 'integracoes'
    if path.startswith('/auditoria'):return 'auditoria'
    if path.startswith('/usuarios'):return 'usuarios'
    return None


def legacy_role(level: str) -> str:
    if level not in LEVELS:raise ValueError('Nível de acesso inválido')
    return 'administrador' if level == 'administrativo' else 'responsavel'
