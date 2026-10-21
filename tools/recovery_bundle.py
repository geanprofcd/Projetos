"""Arquivo de recuperacao cifrado. Nao acessa banco, rede ou credenciais.

Chave separada do arquivo; nunca publicar chave/backup no Git. O manifesto
verifica conteudo antes de escrever em um diretorio NOVO de restauracao.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import zipfile

MAGIC = b'VENDRA-RECOVERY-1\0'


def _aes():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM


def _name(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or path.as_posix() != value or '\\' in value or ':' in value or any(p in ('..', '.') for p in value.split('/')):
        raise ValueError('Caminho de arquivo invalido no backup.')
    return path.as_posix()


def seal(files: dict[str, bytes], archive: Path, key_file: Path) -> dict:
    archive, key_file = archive.resolve(), key_file.resolve()
    if archive.exists() or key_file.exists() or archive.parent == key_file.parent:
        raise ValueError('Backup e chave novos, em pastas separadas, sao obrigatorios.')
    entries = {_name(name): data for name, data in files.items()}
    if 'manifest.json' in entries or not entries:
        raise ValueError('Conjunto de arquivos invalido.')
    manifest = {'format': 1, 'files': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                for name, data in entries.items()}}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name, data in entries.items():
            bundle.writestr(name, data)
        bundle.writestr('manifest.json', json.dumps(manifest, sort_keys=True))
    key, nonce = os.urandom(32), os.urandom(12)
    encrypted = MAGIC + nonce + _aes()(key).encrypt(nonce, stream.getvalue(), MAGIC)
    archive.parent.mkdir(parents=True, exist_ok=True)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    # Exclusivo: nunca sobrescrever uma chave ou backup existente.
    with key_file.open('xb') as target:
        target.write(key)
    os.chmod(key_file, 0o600)
    with archive.open('xb') as target:
        target.write(encrypted)
    return {'files': len(entries), 'bytes': len(encrypted), 'sha256': hashlib.sha256(encrypted).hexdigest()}


def restore(archive: Path, key_file: Path, destination: Path) -> dict:
    destination = destination.resolve()
    if destination.exists():
        raise ValueError('Restaurar somente em diretorio novo; nunca sobrescrever ambiente.')
    encrypted = archive.read_bytes()
    if not encrypted.startswith(MAGIC):
        raise ValueError('Formato de backup invalido.')
    start = len(MAGIC)
    clear = _aes()(key_file.read_bytes()).decrypt(encrypted[start:start+12], encrypted[start+12:], MAGIC)
    files = {}
    with zipfile.ZipFile(io.BytesIO(clear)) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Arquivos duplicados no backup.')
        manifest = json.loads(bundle.read('manifest.json'))
        if manifest.get('format') != 1 or set(names) != {*manifest['files'], 'manifest.json'}:
            raise ValueError('Manifesto de backup inconsistente.')
        for name, info in manifest['files'].items():
            safe = _name(name)
            data = bundle.read(name)
            if len(data) != info['bytes'] or hashlib.sha256(data).hexdigest() != info['sha256']:
                raise ValueError('Integridade do backup invalida.')
            files[safe] = data
    # Toda autenticacao/integridade/caminhos validados ANTES de criar o destino.
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        target = destination.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
    return {'files': len(files), 'verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['seal', 'restore'])
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--key', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.operation == 'seal':
        if not args.source or not args.source.is_dir():
            parser.error('--source deve ser uma pasta privada previamente revisada.')
        files = {}
        for path in args.source.rglob('*'):
            if path.is_symlink():
                raise ValueError('Links simbolicos nao sao aceitos.')
            if path.is_file():
                if path.name == '.env' or path.name.startswith('.env.'):
                    raise ValueError('Perfis .env estao fora deste procedimento de backup.')
                files[path.relative_to(args.source).as_posix()] = path.read_bytes()
        result = seal(files, args.archive, args.key)
    else:
        if not args.destination:
            parser.error('--destination e obrigatorio.')
        result = restore(args.archive, args.key, args.destination)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
