"""Start the integrated STAGING portal with an explicit private profile."""
import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Portal STAGING integrado; transporte exige flag explicita.')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    from dotenv import dotenv_values
    from tools.staging_guard import assert_staging
    from app.core.config import Settings, get_settings
    if not args.config.is_file():
        parser.error('Perfil STAGING nao encontrado.')
    values = {key: str(value or '') for key, value in dotenv_values(args.config).items()}
    assert_staging(values)
    # Do not inherit settings or fall back to the original .env.
    for name in Settings.model_fields:
        os.environ.pop(name.upper(), None)
    os.environ.update(values)
    os.environ['VENDRA_ENV_FILE'] = ''
    get_settings.cache_clear()
    settings = get_settings()
    if args.check:
        print('Perfil explicito STAGING aprovado; transporte '+('habilitado' if settings.dispatch_transport_enabled else 'desativado')+'.')
        return
    import uvicorn
    uvicorn.run('app.staging_h1_006h:app', host='127.0.0.1', port=8011, access_log=False)


if __name__ == '__main__':
    main()
