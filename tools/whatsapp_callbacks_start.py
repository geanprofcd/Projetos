"""python -X utf8 -m tools.whatsapp_callbacks_start --config ARQUIVO_EXCLUSIVO"""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Ponte de entrada/status sem env implicito ou envio.')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8012)
    args = parser.parse_args()
    if args.port in (8010, 8011) or not 1024 <= args.port <= 65535:
        parser.error('Use porta separada de 8010/8011.')
    from app.whatsapp_callbacks import create_app, load_config
    import uvicorn
    uvicorn.run(create_app(load_config(args.config.resolve())), host='127.0.0.1',
                port=args.port, access_log=False)


if __name__ == '__main__':
    main()
