"""Carrega e valida a configuracao exclusiva para a instancia H1-005B2."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import dotenv_values
from tools.staging_guard import assert_staging

CONFIG=Path('.env.h1_005b2')

def load():
    if not CONFIG.is_file():
        raise RuntimeError('Falta .env.h1_005b2. Execute: python -m tools.staging_setup')
    values=dotenv_values(CONFIG)
    env={k:str(v or '') for k,v in values.items()}
    assert_staging(env)
    # Sempre prevalecem os dados explicitos da copia de testes, nao .env principal.
    os.environ.update(env)
    return env
