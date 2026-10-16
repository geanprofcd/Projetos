import unittest
import httpx
from app.db.http_client import DatabaseHttpClient


class DatabaseTransportTests(unittest.TestCase):
    def test_disconnected_read_recovers_once(self):
        calls=[]
        def handle(req):
            calls.append(req.method)
            if len(calls)==1: raise httpx.RemoteProtocolError('disconnected')
            return httpx.Response(200,json={'ok':True})
        with DatabaseHttpClient(transport=httpx.MockTransport(handle)) as c:
            self.assertEqual(c.get('https://db.test').json(),{'ok':True})
        self.assertEqual(calls,['GET','GET'])

    def test_writes_are_never_replayed(self):
        for method in ('POST','PATCH','PUT','DELETE'):
            with self.subTest(method=method):
                calls=[]
                def handle(req):
                    calls.append(req.method)
                    raise httpx.RemoteProtocolError('uncertain write')
                with DatabaseHttpClient(transport=httpx.MockTransport(handle)) as c:
                    with self.assertRaises(httpx.RemoteProtocolError):
                        c.request(method,'https://db.test')
                self.assertEqual(calls,[method])

    def test_read_failure_is_bounded(self):
        calls=[]
        def handle(req):
            calls.append(req.method)
            raise httpx.ReadError('offline')
        with DatabaseHttpClient(transport=httpx.MockTransport(handle)) as c:
            with self.assertRaises(httpx.ReadError):c.get('https://db.test')
        self.assertEqual(len(calls),2)

    def test_authentication_error_is_not_retried(self):
        calls=[]
        def handle(req):
            calls.append(req.method)
            return httpx.Response(401)
        with DatabaseHttpClient(transport=httpx.MockTransport(handle)) as c:
            self.assertEqual(c.get('https://db.test').status_code,401)
        self.assertEqual(len(calls),1)
