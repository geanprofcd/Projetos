import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from app.services import user_service as service


class InvitationLinkTests(unittest.TestCase):
    actor = {'id':'actor','role':'administrador','access_level':'administrativo'}

    def settings(self, **extra):
        return SimpleNamespace(demo_mode=False, is_production=True, invitation_delivery='link',
                               public_app_url='https://vendra.example', **extra)

    def database(self):
        db=MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
        return db

    def test_link_delivery_keeps_only_hash_and_never_calls_smtp(self):
        db=self.database()
        with patch.object(service,'get_settings',return_value=self.settings()), patch.object(service,'get_admin_client',return_value=db), patch.object(service,'_smtp_send') as smtp:
            result=service.create_invite(actor=self.actor,name='Nova Pessoa',email='pessoa@example.org',access_level='comercial')
        self.assertEqual(result['status'],'manual_link')
        token=result['invitation_url'].rsplit('/',1)[-1]
        saved=db.table.return_value.insert.call_args.args[0]
        self.assertEqual(saved['token_hash'],hashlib.sha256(token.encode()).hexdigest())
        self.assertNotIn(token,str(saved))
        db.table.return_value.update.return_value.eq.return_value.in_.assert_called_once_with('status',['pending','sent'])
        smtp.assert_not_called()

    def test_production_link_requires_https_before_writing(self):
        settings=self.settings();settings.public_app_url='http://localhost:8010'
        with patch.object(service,'get_settings',return_value=settings),patch.object(service,'get_admin_client') as db:
            with self.assertRaises(service.UserError):service.create_invite(actor=self.actor,name='Nova Pessoa',email='pessoa@example.org',access_level='comercial')
        db.assert_not_called()

    def test_delegated_commercial_cannot_invite_admin(self):
        actor=dict(self.actor,role='responsavel',access_level='comercial',can_manage_users=True)
        with patch.object(service,'get_admin_client') as db:
            with self.assertRaises(service.UserError):service.create_invite(actor=actor,name='Nova Pessoa',email='pessoa@example.org',access_level='administrativo')
        db.assert_not_called()

    def test_explicit_smtp_retains_email_delivery(self):
        settings=self.settings();settings.invitation_delivery='smtp'
        with patch.object(service,'get_settings',return_value=settings),patch.object(service,'get_admin_client',return_value=self.database()),patch.object(service,'_smtp_send') as smtp:
            result=service.create_invite(actor=self.actor,name='Nova Pessoa',email='pessoa@example.org',access_level='comercial')
        self.assertEqual(result['status'],'sent')
        self.assertNotIn('invitation_url',result)
        smtp.assert_called_once()
