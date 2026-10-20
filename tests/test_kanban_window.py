import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock
from app.services.kanban_window_service import parse_windows, list_kanban_windows


class KanbanWindowTests(unittest.TestCase):
    def test_untrusted_windows_do_not_expand_scope(self):
        for value in ([], {'unknown': 0}, {'a': -1}, {'a': True}, {'a': 1.5}, {'a': 100_000_000}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_windows(value, {'a'})
        self.assertEqual(parse_windows({'a': 9880}, {'a'}), {'a': 9880})

    def test_ten_thousand_total_stays_separate_from_window(self):
        db = Mock()
        db.rpc.return_value.execute.return_value = SimpleNamespace(data=[{
            'stage_id': 'a', 'count': 10000, 'total': 10000, 'offset': 9880,
            'cards': [{'id': str(i), 'calculated_value': 1} for i in range(120)]}])
        with patch('app.services.kanban_window_service.get_admin_client', return_value=db):
            columns = list_kanban_windows({'id': 'f', 'stages': [{'id': 'a'}]}, windows={'a': 9880})
        self.assertEqual(columns[0]['count'], 10000)
        self.assertEqual(len(columns[0]['cards']), 120)
        self.assertEqual(db.rpc.call_args.args[1]['p_limit'], 120)
        self.assertEqual(columns[0]['offset'], 9880)

    def test_fail_closed_if_database_contract_is_unbounded(self):
        db = Mock()
        db.rpc.return_value.execute.return_value = SimpleNamespace(data=[{
            'stage_id': 'a', 'cards': [{} for _ in range(121)]}])
        with patch('app.services.kanban_window_service.get_admin_client', return_value=db), self.assertRaises(ValueError):
            list_kanban_windows({'id': 'f', 'stages': [{'id': 'a'}]})


if __name__ == '__main__':
    unittest.main()
