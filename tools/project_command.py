from __future__ import annotations

import argparse
import hashlib
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def extract_setting(name: str, default: str = "") -> str:
    text = read_text(ROOT / "app/core/config.py")
    match = re.search(rf"^\s*{re.escape(name)}:\s*str\s*=\s*[\"']([^\"']+)[\"']", text, re.MULTILINE)
    return match.group(1) if match else default


def extract_routes() -> list[str]:
    routes: list[str] = []

    main = read_text(ROOT / "app/main.py")
    for method, path in re.findall(r'@app\.(get|post|put|patch|delete)\([\"\']([^\"\']+)[\"\']', main):
        routes.append(f"{method.upper()} {path}")

    routers_dir = ROOT / "app/routers"
    for file in sorted(routers_dir.glob("*.py")):
        text = read_text(file)
        prefix_match = re.search(r"APIRouter\(prefix=[\"']([^\"']*)[\"']", text)
        prefix = prefix_match.group(1) if prefix_match else ""
        for method, path in re.findall(r'@router\.(get|post|put|patch|delete)\([\"\']([^\"\']*)[\"\']', text):
            full = f"{prefix}{path}" or "/"
            routes.append(f"{method.upper()} {full}")
    return sorted(set(routes))


def extract_env_vars() -> list[str]:
    vars_: list[str] = []
    for line in read_text(ROOT / ".env.example").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            vars_.append(line.split("=", 1)[0])
    return vars_


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_files(pattern: str) -> list[str]:
    return sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in ROOT.glob(pattern) if p.is_file())


def build_pdf_snapshot(output: Path) -> None:
    app_name = extract_setting("app_name", "VENDRA")
    app_version = extract_setting("app_version", "desconhecida")
    routes = extract_routes()
    env_vars = extract_env_vars()
    requirements = [line.strip() for line in read_text(ROOT / "requirements.txt").splitlines() if line.strip()]
    templates = relative_files("app/templates/**/*.html")
    migrations = relative_files("sql/migrations/*.sql")
    login_images = relative_files("app/static/img/login/*")
    css_files = relative_files("app/static/css/*.css")
    js_files = relative_files("app/static/js/*.js")
    screenshots = relative_files("docs/screenshots/*")

    artifacts = []
    for name in ["Vendra.exe", "README.md", "PROJECT_STATE.md", "CHANGELOG.md"]:
        path = ROOT / name
        if path.exists():
            artifacts.append((name, file_sha256(path)))

    lines = [
        f"# Snapshot automático para PDF — {app_name}",
        "",
        f"Gerado em (America/Sao_Paulo): {datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(timespec='seconds')}",
        f"Versão detectada: {app_version}",
        "",
        "Este arquivo é gerado pelo subcomando `pdf` e deve ser conferido junto com o código antes de gerar o Documento Mestre.",
        "",
        "## Rotas detectadas",
        "",
        *[f"- `{route}`" for route in routes],
        "",
        "## Variáveis de ambiente declaradas",
        "",
        *[f"- `{name}`" for name in env_vars],
        "",
        "## Dependências declaradas",
        "",
        *[f"- `{dep}`" for dep in requirements],
        "",
        "## Templates atuais",
        "",
        *[f"- `{name}`" for name in templates],
        "",
        "## CSS atual",
        "",
        *[f"- `{name}`" for name in css_files],
        "",
        "## JavaScript atual",
        "",
        *[f"- `{name}`" for name in js_files],
        "",
        "## Imagens do login",
        "",
        *[f"- `{name}`" for name in login_images],
        "",
        "## Screenshots de referência",
        "",
        *[f"- `{name}`" for name in screenshots],
        "",
        "## Migrations",
        "",
        *[f"- `{name}`" for name in migrations],
        "",
        "## Hashes de artefatos-chave",
        "",
        *[f"- `{name}` — `{sha}`" for name, sha in artifacts],
        "",
        "## Fontes humanas obrigatórias para consolidação",
        "",
        "- `PROJECT_STATE.md`",
        "- `CHANGELOG.md`",
        "- `AGENTS.md`",
        "- `docs/commands/pdf.md`",
        "- Documento Mestre/PDF anterior, apenas como histórico e planejamento.",
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Snapshot atualizado: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="project_command", description="Comandos de continuidade do projeto VENDRA")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pdf_parser = subparsers.add_parser("pdf", help="Atualiza o snapshot técnico obrigatório antes de gerar o Documento Mestre")
    pdf_parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/PDF_PROJECT_SNAPSHOT.md",
        help="Arquivo Markdown de snapshot técnico",
    )

    args = parser.parse_args()
    if args.command == "pdf":
        build_pdf_snapshot(args.output)


if __name__ == "__main__":
    main()
