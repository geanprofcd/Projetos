"""Prévia local da interface comercial usando apenas o perfil STAGING explícito."""
import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Interface comercial em cópia, banco STAGING e porta local8014.')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    from dotenv import dotenv_values
    from tools.staging_guard import assert_staging
    from app.core.config import Settings, get_settings
    if not args.config.is_file():
        parser.error('Perfil explícito STAGING ausente.')
    values = {k: str(v or '') for k, v in dotenv_values(args.config).items()}
    assert_staging(values)
    for name in Settings.model_fields:
        os.environ.pop(name.upper(), None)
    os.environ.update(values)
    os.environ['VENDRA_ENV_FILE'] = ''
    get_settings.cache_clear()
    if get_settings().dispatch_transport_enabled:
        parser.error('Prévia comercial exige transporte de disparos desligado.')
    if args.check:
        print('Prévia comercial aprovada: cópia local8014, banco STAGING, sem transporte de disparos.')
        return
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=8014, access_log=False)


if __name__ == '__main__':
    main()
