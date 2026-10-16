"""Transporte do banco: HTTP/1.1 e uma recuperacao apenas para leituras."""
import httpx


class DatabaseHttpClient(httpx.Client):
    def request(self, method, url, **kwargs):
        try:
            return super().request(method, url, **kwargs)
        except (httpx.RemoteProtocolError, httpx.ReadError):
            # Nunca repetir RPC, login, insert/update/delete ou envio incerto.
            if method.upper() not in ('GET', 'HEAD'):
                raise
            return super().request(method, url, **kwargs)


def create_database_http_client():
    return DatabaseHttpClient(
        http2=False,
        timeout=httpx.Timeout(30, connect=10),
        limits=httpx.Limits(max_connections=30, max_keepalive_connections=10,
                           keepalive_expiry=5),
    )
