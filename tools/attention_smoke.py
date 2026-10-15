"""Smoke local: marcos temporais e avisos de falta de resposta 0.0.23."""
from datetime import datetime, timedelta, timezone
from app.services.ticket_attention_service import date_br, time_br, summarize_ticket, ALERT_AFTER_SECONDS

BASE = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)  # 12:00 Brasília
TICKET = {'id': 't-1', 'created_at': '2026-10-12T14:50:00+00:00', 'status': 'em_atendimento'}

def message(id, minute, direction, *, internal=False, delivery=None):
    return {'id': id, 'created_at': (BASE + timedelta(minutes=minute)).isoformat(), 'direction': direction, 'is_internal': internal, 'delivery_status': delivery}


def test_ptbr_formats_and_dates_without_timezone_shift():
    assert date_br('2026-10-12') == '12/10/2026'
    assert date_br('2026-10-12T01:00:00+00:00') == '11/10/2026'
    assert date_br('2026-10-12T15:20:00+00:00') == '12/10/2026'
    assert time_br('2026-10-12T17:20:00+00:00') == '14:20'
    assert date_br(None) == '—' and time_br(None) == '—'


def test_first_response_and_exact_30_minute_threshold():
    messages = [message('a', 0, 'outbound'), message('b', 2, 'inbound')]
    before = summarize_ticket(TICKET, messages, now=BASE+timedelta(minutes=31,seconds=59))
    after = summarize_ticket(TICKET, messages, now=BASE+timedelta(minutes=32))
    assert before['arrival_date'] == '12/10/2026'
    assert before['first_reply_time'] == '12:02'
    assert not before['pending']
    assert after['pending'] and after['pending_minutes'] == 30
    assert after['alert_key'].startswith('t-1:')


def test_internal_notes_dont_clear_alert_but_sent_reply_does():
    messages = [message('a', 0, 'inbound'), message('b', 20, 'outbound',internal=True)]
    assert summarize_ticket(TICKET, messages,now=BASE+timedelta(minutes=31))['pending']
    messages.append(message('c', 31, 'outbound', delivery='sent'))
    assert not summarize_ticket(TICKET,messages,now=BASE+timedelta(minutes=35))['pending']
    messages.append(message('d', 36, 'inbound'))
    assert summarize_ticket(TICKET,messages,now=BASE+timedelta(minutes=66))['pending']


def test_failed_outbound_and_closed_ticket():
    messages = [message('a',0,'inbound'),message('b',10,'outbound',delivery='failed')]
    assert summarize_ticket(TICKET,messages,now=BASE+timedelta(minutes=30))['pending']
    assert not summarize_ticket({**TICKET,'status':'finalizado'},messages,now=BASE+timedelta(minutes=40))['pending']


def test_newer_inbound_resets_timer():
    messages=[message('a',0,'inbound'),message('b',25,'inbound')]
    assert not summarize_ticket(TICKET,messages,now=BASE+timedelta(minutes=40))['pending']
    assert summarize_ticket(TICKET,messages,now=BASE+timedelta(minutes=55))['pending']
    assert summarize_ticket(TICKET,messages,now=BASE+timedelta(minutes=55))['first_reply_time']=='12:00'


def test_no_inbound_no_alert():
    assert not summarize_ticket(TICKET,[message('a',0,'outbound')],now=BASE+timedelta(days=2))['pending']
    assert summarize_ticket(TICKET,[],now=BASE+timedelta(days=2))['first_reply_time']=='—'

if __name__=='__main__':
    import pytest
    raise SystemExit(pytest.main([__file__,'-q']))
