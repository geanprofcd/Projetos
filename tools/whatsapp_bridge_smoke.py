from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def request_json(url: str, *, method: str = "GET", secret: str | None = None, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if secret:
        headers["X-Vendra-Webhook-Secret"] = secret
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw or "{}")
        except json.JSONDecodeError:
            body = {"raw": raw}
        return exc.code, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test do bridge WhatsApp/Make -> VENDRA")
    parser.add_argument("--base-url", required=True, help="Ex.: https://abc.trycloudflare.com")
    parser.add_argument("--public-id", required=True, help="Public ID do webhook configurado")
    parser.add_argument("--secret", required=True, help="Segredo do webhook")
    parser.add_argument("--phone", default="5511999999999")
    parser.add_argument("--name", default="Cliente Smoke 0.5.5")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    health_status, health = request_json(f"{base}/health")
    print("HEALTH", health_status, json.dumps(health, ensure_ascii=False))
    if health_status != 200 or health.get("status") != "ok":
        print("FALHA: /health não está saudável.", file=sys.stderr)
        return 2

    external_id = f"smoke-v054-{int(time.time())}"
    payload = {
        "phone": args.phone,
        "name": args.name,
        "message": "Teste controlado VENDRA 0.0.3 - entrada e idempotencia",
        "external_message_id": external_id,
    }
    url = f"{base}/webhooks/configurados/{args.public_id}"
    first_status, first = request_json(url, method="POST", secret=args.secret, payload=payload)
    second_status, second = request_json(url, method="POST", secret=args.secret, payload=payload)

    print("PRIMEIRO ENVIO", first_status, json.dumps(first, ensure_ascii=False))
    print("REENVIO", second_status, json.dumps(second, ensure_ascii=False))

    if first_status not in {200, 202} or first.get("duplicate") is True:
        print("FALHA: primeiro envio não foi aceito como novo evento.", file=sys.stderr)
        return 3
    if second_status not in {200, 202} or second.get("duplicate") is not True:
        print("FALHA: reenvio não confirmou idempotência.", file=sys.stderr)
        return 4

    print("OK: health, entrada autenticada e idempotência validados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
