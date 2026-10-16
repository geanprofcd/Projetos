import unittest
from datetime import datetime, timedelta, timezone

from app.services.ticket_attention_service import summarize_ticket


class TicketAttentionTests(unittest.TestCase):
    origin = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)

    def message(self, minute=0, direction='inbound', **extra):
        return dict(id=str(minute), created_at=(self.origin + timedelta(minutes=minute)).isoformat(),
                    direction=direction, **extra)

    def summary(self, messages, seconds=1800, status='novo'):
        return summarize_ticket({'id': 'test', 'status': status}, messages,
                                now=self.origin + timedelta(seconds=seconds))

    def test_no_alert_before_thirty_minutes(self):
        self.assertFalse(self.summary([self.message()], seconds=1799)['pending'])

    def test_alert_at_thirty_minutes(self):
        result = self.summary([self.message()])
        self.assertTrue(result['pending'])
        self.assertEqual(result['pending_minutes'], 30)
        self.assertEqual(result['pending_since'], self.origin.isoformat())

    def test_latest_lead_message_restarts_clock_and_alert_identity(self):
        first = self.summary([self.message()])
        rows = [self.message(), self.message(20)]
        self.assertFalse(self.summary(rows)['pending'])
        second = self.summary(rows, seconds=3000)
        self.assertTrue(second['pending'])
        self.assertNotEqual(first['alert_key'], second['alert_key'])
        self.assertEqual(second['pending_minutes'], 30)

    def test_human_and_ai_sent_delivered_or_read_clear_alert(self):
        for sender in ('human', 'ai'):
            for status in ('sent', 'delivered', 'read'):
                with self.subTest(sender=sender, status=status):
                    rows = [self.message(), self.message(1, 'outbound', sender_kind=sender, delivery_status=status)]
                    result = self.summary(rows)
                    self.assertFalse(result['pending'])
                    self.assertIsNone(result['alert_key'])

    def test_reserved_unsent_failed_and_cancelled_do_not_clear_alert(self):
        for status in ('pending', 'claimed', 'failed', 'cancelled'):
            with self.subTest(status=status):
                self.assertTrue(self.summary([self.message(), self.message(1, 'outbound', delivery_status=status)])['pending'])

    def test_internal_note_does_not_clear_alert(self):
        self.assertTrue(self.summary([self.message(), self.message(1, 'outbound', is_internal=True, delivery_status='sent')])['pending'])

    def test_previous_reply_does_not_answer_new_inbound(self):
        self.assertTrue(self.summary([self.message(-1, 'outbound', delivery_status='sent'), self.message()])['pending'])

    def test_new_inbound_after_answer_starts_new_wait(self):
        rows = [self.message(-60), self.message(-59, 'outbound', delivery_status='sent'), self.message()]
        self.assertTrue(self.summary(rows)['pending'])

    def test_closed_ticket_has_no_alert(self):
        for status in ('finalizado', 'cancelado'):
            with self.subTest(status=status):
                self.assertFalse(self.summary([self.message()], status=status)['pending'])

    def test_no_inbound_has_no_alert(self):
        self.assertFalse(self.summary([self.message(-1, 'outbound', delivery_status='sent')])['pending'])
