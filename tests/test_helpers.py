# tests/test_helpers.py

from unittest.mock import patch, mock_open, MagicMock

import typer

from app.models import Group
from app.utils.helpers import (
    set_active_group_id,
    get_active_group_id,
    clear_active_group,
    get_db,
    get_db_and_group,
    resolve_or_prompt_group,
    min_cash_flow_settlements
)
from collections import Counter
from tests.base import BaseCLITest


class TestHelpers(BaseCLITest):
    def test_set_active_group_id(self):
        """
        Ensure group ID is correctly written to the session file.
        """
        with patch("builtins.open", mock_open()) as mocked_file:
            set_active_group_id(1)
            mocked_file.assert_called_once_with(".eco_session", "w")
            mocked_file().write.assert_called_once_with("1")

    def test_get_active_group_id_exists(self):
        """
        Ensure correct group ID is returned from session file if it exists.
        """
        with patch("os.path.exists", return_value=True), patch("builtins.open",
                                                               mock_open(read_data="42")) as mocked_file:
            result = get_active_group_id()
            self.assertEqual(result, 42)
            mocked_file.assert_called_once_with(".eco_session", "r")

    def test_get_active_group_id_not_exists(self):
        """
        Ensure None is returned if session file does not exist.
        """
        with patch("os.path.exists", return_value=False):
            self.assertIsNone(get_active_group_id())

    def test_clear_active_group(self):
        """
        Ensure session file is removed when clearing active group.
        """
        with patch("os.path.exists", return_value=True), patch("os.remove") as mocked_remove:
            clear_active_group()
            mocked_remove.assert_called_once_with(".eco_session")

    def test_get_db_context_success(self):
        """
        Ensure get_db yields the mocked DB session and calls close without rollback.
        """
        with get_db() as db:
            self.assertEqual(db, self.mock_db)
        self.mock_db.close.assert_called_once()
        self.mock_db.rollback.assert_not_called()

    def test_get_db_context_exception(self):
        """
        Ensure get_db rolls back and closes if an exception is raised inside the block.
        """
        self.mock_db.__enter__.side_effect = None  # reset if anything altered
        with patch("app.utils.helpers.SessionLocal", return_value=self.mock_db):
            with self.assertRaises(Exception):
                with get_db():
                    raise Exception("Mocked DB error")
        self.mock_db.rollback.assert_called_once()
        self.mock_db.close.assert_called_once()

    def test_get_db_and_group_success(self):
        """
        Ensure get_db_and_group yields valid DB and group, commits and closes.
        """
        with get_db_and_group() as (db, group):
            self.assertEqual(db, self.mock_db)
            self.assertEqual(group.id, self.mock_group.id)
        self.mock_db.commit.assert_called_once()
        self.mock_db.close.assert_called_once()

    def test_get_db_and_group_group_not_found(self):
        """
        Ensure typer.Exit is raised and rollback is called if group cannot be found.
        """
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = None
        with self.assertRaises(typer.Exit):
            with get_db_and_group():
                pass
        self.mock_db.rollback.assert_called_once()
        self.mock_db.close.assert_called_once()

    def test_resolve_or_prompt_group_auto_select(self):
        """
        If only one group exists, it should be auto-selected and returned.
        """
        self.mock_db.query.return_value.all.return_value = [self.mock_group]
        with patch("app.utils.helpers.get_active_group_id", return_value=None), \
                patch("app.utils.helpers.set_active_group_id") as mock_set_id:
            gid = resolve_or_prompt_group(self.mock_db)
            self.assertEqual(gid, 1)
            mock_set_id.assert_called_once_with(1)

    def test_resolve_or_prompt_group_user_select_valid(self):
        """
        If multiple groups exist and user selects a valid one, it should be returned.
        """
        group2 = MagicMock(spec=Group)
        group2.id = 2
        group2.name = "SecondGroup"
        self.mock_db.query.return_value.all.return_value = [self.mock_group, group2]
        with patch("app.utils.helpers.get_active_group_id", return_value=None), \
                patch("typer.prompt", return_value="2"), patch("app.utils.helpers.set_active_group_id") as mock_set_id:
            gid = resolve_or_prompt_group(self.mock_db)
            self.assertEqual(gid, 2)
            mock_set_id.assert_called_once_with(2)

    def test_resolve_or_prompt_group_user_select_invalid(self):
        """
        If user selects an invalid group number, typer.Exit should be raised.
        """
        group2 = MagicMock(spec=Group)
        group2.id = 2
        group2.name = "SecondGroup"
        self.mock_db.query.return_value.all.return_value = [self.mock_group, group2]
        with patch("app.utils.helpers.get_active_group_id", return_value=None), \
                patch("typer.prompt", return_value="x"):
            with self.assertRaises(typer.Exit):
                resolve_or_prompt_group(self.mock_db)

    def test_min_cash_flow_empty_and_one_sided(self):
        # No balances
        self.assertEqual(min_cash_flow_settlements({}), [])

        # Only creditors
        self.assertEqual(min_cash_flow_settlements({"A": 10.0, "B": 0.0}), [])

        # Only debtors
        self.assertEqual(min_cash_flow_settlements({"A": -10.0}), [])

        # All zeros
        self.assertEqual(min_cash_flow_settlements({"A": 0.0, "B": 0.0}), [])

    def test_min_cash_flow_simple_pair(self):
        balances = {"A": -10.0, "B": 10.0}
        result = min_cash_flow_settlements(balances)
        self.assertEqual(result, [("A", "B", 10.0)])

    def test_min_cash_flow_multiple_participants(self):
        # Debtors: A=10, B=20 ; Creditors: C=15, D=15
        balances = {"A": -10.0, "B": -20.0, "C": 15.0, "D": 15.0}
        result = min_cash_flow_settlements(balances)
        # Algorithm matches largest debtor with the largest creditor, then proceeds
        expected = [("B", "C", 15.0), ("A", "D", 10.0), ("B", "D", 5.0)]
        # Normalize result order for comparison since order may vary
        self.assertEqual(Counter(result), Counter(expected))

        # Conservation: total paid == total received == total positive == total negative
        total_paid = round(sum(a for _, _, a in result), 2)
        total_pos = round(sum(v for v in balances.values() if v > 0), 2)
        total_neg = round(sum(-v for v in balances.values() if v < 0), 2)
        self.assertEqual(total_paid, total_pos)
        self.assertEqual(total_paid, total_neg)

        # No self-transfers
        self.assertTrue(all(d != c for d, c, _ in result))

    def test_min_cash_flow_rounding_and_epsilon_zeroing(self):
        # Tiny residuals below eps (0.01) are zeroed
        balances_tiny = {"A": -0.004, "B": 0.004}
        self.assertEqual(min_cash_flow_settlements(balances_tiny), [])

        # Values near cents should round cleanly and still settle
        balances_near = {"A": -10.004, "B": 10.004}
        result = min_cash_flow_settlements(balances_near)
        self.assertEqual(result, [("A", "B", 10.0)])

    def test_min_cash_flow_unbalanced_lengths(self):
        # More creditors than debtors
        balances = {"A": -25.0, "B": 10.0, "C": 10.0, "D": 5.0}
        result = min_cash_flow_settlements(balances)
        # Expected matches in descending order
        expected = [("A", "B", 10.0), ("A", "C", 10.0), ("A", "D", 5.0)]
        self.assertEqual(result, expected)

        # Conservation
        total_paid = round(sum(a for _, _, a in result), 2)
        total_pos = round(sum(v for v in balances.values() if v > 0), 2)
        total_neg = round(sum(-v for v in balances.values() if v < 0), 2)
        self.assertEqual(total_paid, total_pos)
        self.assertEqual(total_paid, total_neg)

