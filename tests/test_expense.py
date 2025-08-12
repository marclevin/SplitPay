from datetime import datetime
from unittest.mock import MagicMock

from app.models import Member, Expense, ExpenseSplit
from cli import app
from tests.base import BaseCLITest


class TestExpenseCommands(BaseCLITest):
    def setUp(self):
        super().setUp()
        # Create mock members for testing
        self.mock_member1 = MagicMock(spec=Member)
        self.mock_member1.id = 1
        self.mock_member1.name = "Member1"
        self.mock_member1.group_id = self.mock_group.id

        self.mock_member2 = MagicMock(spec=Member)
        self.mock_member2.id = 2
        self.mock_member2.name = "Member2"
        self.mock_member2.group_id = self.mock_group.id

        # Create mock expense for testing
        self.mock_expense = MagicMock(spec=Expense)
        self.mock_expense.id = 1
        self.mock_expense.description = "Test Expense"
        self.mock_expense.amount = 100.0
        self.mock_expense.date = datetime.now()
        self.mock_expense.paid_by_id = self.mock_member1.id
        self.mock_expense.group_id = self.mock_group.id

        # Create mock expense split for testing
        self.mock_split = MagicMock(spec=ExpenseSplit)
        self.mock_split.expense_id = self.mock_expense.id
        self.mock_split.member_id = self.mock_member1.id
        self.mock_split.share_amount = 50.0
        self.mock_split.member = self.mock_member1

    # Command: expense add
    def test_add_expense_single_member(self):
        """Test adding an expense paid by a single member"""
        # Mock member query
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_member1
        self.mock_db.query.return_value.filter.return_value.all.return_value = [self.mock_member1]

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(
                app,
                ["expense", "add"],
                input="100\nMember1\nTest Expense\n2024-01-01\n\n"
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("✅ Expense 'Test Expense' added and split between Member1", result.stdout)

    def test_add_expense_multiple_members(self):
        """Test adding an expense split between multiple members"""
        # Mock member queries
        self.mock_db.query.return_value.filter.return_value.first.side_effect = [
            self.mock_member1,  # For payer check
            self.mock_member1,  # For first member in split
            self.mock_member2,  # For second member in split
        ]
        self.mock_db.query.return_value.filter.return_value.all.return_value = [
            self.mock_member1,
            self.mock_member2
        ]

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(
                app,
                ["expense", "add"],
                input="100\nMember1\nTest Expense\n2024-01-01\nMember1\nMember2\n\n"
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("✅ Expense 'Test Expense' added and split between Member1, Member2", result.stdout)

    def test_add_expense_payer_not_found(self):
        """Test adding an expense with a non-existent payer"""
        # Mock member query to return None for payer
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(
                app,
                ["expense", "add"],
                input="100\nNonExistentMember\nTest Expense\n2024-01-01\n\n"
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("❌ Payer 'NonExistentMember' not found in the selected group", result.stdout)

    def test_add_expense_split_member_not_found(self):
        """Test adding an expense with a non-existent split member"""
        # Create a member that exists but is in a different group
        other_group_member = MagicMock(spec=Member)
        other_group_member.id = 3
        other_group_member.name = "NonExistentMember"
        other_group_member.group_id = 999  # Different group ID

        # Mock member queries
        self.mock_db.query.return_value.filter.return_value.first.side_effect = [
            self.mock_member1,  # For payer check
            other_group_member,  # For split member check - exists but in different group
        ]
        # Mock the final member query that checks group membership
        self.mock_db.query.return_value.filter.return_value.all.return_value = []  # No members found in group

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(
                app,
                ["expense", "add"],
                input="100\nMember1\nTest Expense\n2024-01-01\nNonExistentMember\n\n"
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("❌ Some members in split not found", result.stdout)

    # Command: expense show
    def test_show_expenses(self):
        """Test showing expenses when there are some"""
        # Create separate mock queries for each database call
        mock_expense_query = MagicMock()
        mock_expense_query.filter_by.return_value.all.return_value = [self.mock_expense]
        mock_member_query = MagicMock()
        mock_member_query.filter_by.return_value.first.return_value = self.mock_member1

        mock_split_query = MagicMock()
        mock_split_query.filter_by.return_value.all.return_value = [self.mock_split]

        # Set up the query chain to return different mocks for different calls
        self.mock_db.query.side_effect = [
            mock_expense_query,  # First call: get expenses
            mock_member_query,  # Second call: get payer
            mock_split_query  # Third call: get splits
        ]

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "show"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("📊 Expenses in group 'TestGroup'", result.stdout)

    def test_show_no_expenses(self):
        """Test showing expenses when there are none"""
        # Mock empty expense query
        self.mock_db.query.return_value.filter_by.return_value.all.return_value = []

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "show"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("No expenses found in the current group", result.stdout)
