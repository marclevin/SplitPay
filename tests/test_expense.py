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
        self.mock_member1.color = "red"
        self.mock_member1.group_id = self.mock_group.id

        self.mock_member2 = MagicMock(spec=Member)
        self.mock_member2.id = 2
        self.mock_member2.name = "Member2"
        self.mock_member2.color = "blue"
        self.mock_member2.group_id = self.mock_group.id

        # Create mock expense for testing
        self.mock_expense = MagicMock(spec=Expense)
        self.mock_expense.id = 1
        self.mock_expense.description = "Test Expense"
        self.mock_expense.amount = 100.0
        self.mock_expense.date = datetime.now()
        self.mock_expense.paid_by_id = self.mock_member1.id
        self.mock_expense.group_id = self.mock_group.id
        self.mock_expense.payer = self.mock_member1

        # Create mock expense split for testing
        self.mock_split = MagicMock(spec=ExpenseSplit)
        self.mock_split.expense_id = self.mock_expense.id
        self.mock_split.member_id = self.mock_member1.id
        self.mock_split.share_amount = 50.0
        self.mock_split.member = self.mock_member1

        self.mock_expense.splits = [self.mock_split]

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

    # Command: expense show
    def test_show_expenses(self):
        """Test showing expenses when there are some"""
        # Create separate mock queries for each database call
        # Mock expense query, returning a list with one expense
        self.mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
            self.mock_expense]

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "show"])
            self.assertIn("Expenses in group", result.stdout)
            self.assertEqual(result.exit_code, 0)

    def test_show_no_expenses(self):
        """Test showing expenses when there are none"""
        # Mock empty expense query
        self.mock_db.query.return_value.filter_by.return_value.all.return_value = []

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "show"])
            self.assertEqual(result.exit_code, 0)

    def _wire_delete_query_side_effects(self, *, expense_exists=True, splits_deleted=1):
        """
        Helper to wire distinct query() mocks for Expense, Member, ExpenseSplit.
        """
        q_expense = MagicMock()
        q_member = MagicMock()
        q_split = MagicMock()

        # Expense lookup
        q_expense.filter.return_value.first.return_value = (
            self.mock_expense if expense_exists else None
        )

        # Payer lookup
        q_member.filter_by.return_value.first.return_value = self.mock_member1

        # Splits delete
        q_split.filter_by.return_value.delete.return_value = splits_deleted

        def query_side_effect(model):
            if model is Expense:
                return q_expense
            if model is Member:
                return q_member
            if model is ExpenseSplit:
                return q_split
            return MagicMock()

        self.mock_db.query.side_effect = query_side_effect
        return q_expense, q_member, q_split

    def test_delete_expense_yes_flag_happy_path(self):
        """Deletes an existing expense (skips confirmation with --yes), deletes splits first, commits."""
        # Ensure our mock objects look like real rows
        self.mock_expense.id = 42
        self.mock_expense.description = "Dinner"
        self.mock_expense.amount = 250.0

        self._wire_delete_query_side_effects(expense_exists=True, splits_deleted=2)

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "delete", "42", "--yes"])

        # Output + exit code
        self.assertEqual(result.exit_code, 0)
        self.assertIn("✅ Deleted expense ID 42 ('Dinner') and 2 split(s).", result.stdout)

        # Order of operations: splits deleted -> expense deleted -> commit
        self.mock_db.delete.assert_called_once_with(self.mock_expense)
        self.mock_db.commit.assert_called_once()
        self.mock_db.rollback.assert_not_called()

    def test_delete_expense_not_found(self):
        """If the expense doesn't exist in the active group, prints a message and exits cleanly."""
        self._wire_delete_query_side_effects(expense_exists=False)

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "delete", "999", "--yes"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("❌ Expense ID 999 not found in the current group.", result.stdout)
        self.mock_db.delete.assert_not_called()
        self.mock_db.commit.assert_not_called()

    def test_delete_expense_confirmation_cancel(self):
        """Prompts without --yes and cancels when user responds 'n'."""
        self.mock_expense.id = 7
        self.mock_expense.description = "Snacks"
        self.mock_expense.amount = 80.0

        self._wire_delete_query_side_effects(expense_exists=True, splits_deleted=1)

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "delete", "7"], input="n\n")

        self.assertEqual(result.exit_code, 0)
        self.assertIn("❌ Deletion cancelled", result.stdout)
        self.mock_db.delete.assert_not_called()
        self.mock_db.commit.assert_not_called()
        self.mock_db.rollback.assert_not_called()

    def test_delete_expense_confirmation_proceed(self):
        """Prompts without --yes and proceeds when user responds 'y'."""
        self.mock_expense.id = 8
        self.mock_expense.description = "Taxi"
        self.mock_expense.amount = 120.0

        self._wire_delete_query_side_effects(expense_exists=True, splits_deleted=3)

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "delete", "8"], input="y\n")

        self.assertEqual(result.exit_code, 0)
        self.assertIn("✅ Deleted expense ID 8 ('Taxi') and 3 split(s).", result.stdout)
        self.mock_db.delete.assert_called_once_with(self.mock_expense)
        self.mock_db.commit.assert_called_once()

    def test_delete_expense_failure_rolls_back(self):
        """If deletion fails, we roll back and exit with code=1."""
        self.mock_expense.id = 77
        self.mock_expense.description = "Hotel"

        self._wire_delete_query_side_effects(expense_exists=True, splits_deleted=1)

        # Force an error during db.delete(expense)
        self.mock_db.delete.side_effect = Exception("DB error")

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "delete", "77", "--yes"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("❌ Failed to delete expense ID 77: DB error", result.stdout)
        self.mock_db.rollback.assert_called_once()
        # commit should not have happened
        self.mock_db.commit.assert_not_called()

    # --- Helpers for edit() tests ---

    @staticmethod
    def _mk_split(member, amount):
        s = MagicMock(spec=ExpenseSplit)
        s.member_id = member.id
        s.share_amount = float(amount)
        return s

    def _wire_edit_queries(
            self,
            *,
            expense_exists=True,
            payer_exists=True,
            existing_splits=None,
            member_lookup=None,
    ):
        """
        Wire db.query(...) for models used by edit():
          - Expense: .filter(...).first()
          - Member (by id/group & by name/group): .filter_by(...).first() and .filter(...).first()
          - ExpenseSplit: .filter_by(...).all() and later .filter_by(...).delete()
        """
        if existing_splits is None:
            existing_splits = []
        if member_lookup is None:
            member_lookup = {"Member1": self.mock_member1, "Member2": self.mock_member2}

        # Ensure expense looks like a real row
        self.mock_expense.id = 123
        self.mock_expense.description = "Old desc"
        self.mock_expense.amount = 100.0
        self.mock_expense.date = datetime(2024, 1, 1)
        self.mock_expense.paid_by_id = self.mock_member1.id
        self.mock_expense.group_id = self.mock_group.id

        # Expense query mock
        q_expense = MagicMock()
        q_expense.filter.return_value.first.return_value = self.mock_expense if expense_exists else None

        # Member query mock
        q_member = MagicMock()

        def member_filter_by_side_effect(**kwargs):
            # Handles current payer by id and final payer_name_display by id
            if "id" in kwargs:
                if payer_exists:
                    if kwargs["id"] == self.mock_member1.id:
                        return MagicMock(first=MagicMock(return_value=self.mock_member1))
                    if kwargs["id"] == self.mock_member2.id:
                        return MagicMock(first=MagicMock(return_value=self.mock_member2))
                return MagicMock(first=MagicMock(return_value=None))
            # Could be other filter_by calls; default to Member1
            return MagicMock(first=MagicMock(return_value=self.mock_member1 if payer_exists else None))

        q_member.filter_by.side_effect = member_filter_by_side_effect

        def member_filter_side_effect(*clauses):
            # This handles Member.name == <name> & Member.group_id == group.id
            # We can't easily inspect SQLAlchemy binary expressions; use the prepared lookup
            # We'll just return a .first() whose value we set later in tests by swapping member_lookup.
            # To make it work, we capture the *latest* requested name via a closure.
            resp = MagicMock()

            # default -> first() returns found member or None
            def first():
                # We can't parse expressions; tests will pre-seed member_lookup keys they will input
                # Pop the most recent name from a small queue we stash on the test instance.
                name = getattr(self, "_last_requested_member_name", None)
                return member_lookup.get(name)

            resp.first.side_effect = first
            return resp

        q_member.filter.side_effect = member_filter_side_effect

        # ExpenseSplit query mock
        q_split = MagicMock()
        q_split.filter_by.return_value.all.return_value = existing_splits
        q_split.filter_by.return_value.delete.return_value = len(existing_splits)

        # Side-effect router
        def query_side_effect(model):
            if model is Expense:
                return q_expense
            if model is Member:
                return q_member
            if model is ExpenseSplit:
                return q_split
            return MagicMock()

        self.mock_db.query.side_effect = query_side_effect

    # --- Tests for: expense edit ---

    def test_edit_no_new_splits_keeps_existing(self):
        """
        Edits fields, leaves splits empty => existing splits kept.
        Existing splits sum must match new amount to avoid warning.
        """
        # Arrange existing splits: Member1: 60, Member2: 40 -> sum 100
        splits = [self._mk_split(self.mock_member1, 60), self._mk_split(self.mock_member2, 40)]
        self._wire_edit_queries(existing_splits=splits)

        # Inputs (in order):
        # Description, Amount, Date, Paid by, (Splits loop) Member name => '' to finish
        user_input = "\n".join([
            "New dinner",  # Description
            "100",  # Amount (unchanged)
            "2024-02-02",  # Date
            "Member1",  # Paid by
            "",  # Member name -> finish splits (keep existing)
        ]) + "\n"

        # Track name lookups inside member_filter_side_effect
        self._last_requested_member_name = "Member1"  # payer resolution
        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "edit", "123"], input=user_input)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("✅ Expense ID 123 updated.", result.stdout)
        # Splits kept => no delete + no adds
        self.mock_db.query.assert_called()  # sanity
        self.mock_db.commit.assert_called_once()
        self.mock_db.add.assert_not_called()

    def test_edit_replace_splits_success(self):
        """
        Enters new splits that exactly sum to new amount -> old splits deleted, new inserted, commit.
        """
        # Existing splits (will be replaced)
        splits = [self._mk_split(self.mock_member1, 100)]
        # Member lookups we plan to input
        member_lookup = {"Member2": self.mock_member2, "Member1": self.mock_member1}
        self._wire_edit_queries(existing_splits=splits, member_lookup=member_lookup)

        # New amount 150; two splits: Member1=50, Member2=100
        # Inputs: desc, amount, date, payer, split1 name/amount, split2 name/amount, blank to finish
        seq = [
            "Team lunch",  # Description
            "150",  # Amount
            "2024-03-10",  # Date
            "Member2",  # Paid by
            "Member1", "50",  # Split #1
            "Member2", "100",  # Split #2
            "",  # finish
        ]
        user_input = "\n".join(seq) + "\n"

        # Simulate successive member name lookups in order they appear
        #  - payer "Member2"
        #  - split1 "Member1"
        #  - split2 "Member2"
        for name in ["Member2", "Member1", "Member2"]:
            self._last_requested_member_name = name  # consumed by our member filter mock
            with self.mock_db_and_group(module_path="app.commands.expense"):
                result = self.runner.invoke(app, ["expense", "edit", "123"], input=user_input)
            break  # we run once; the closure reads the last set value on each call

        self.assertEqual(result.exit_code, 0)
        self.assertIn("✅ Expense ID 123 updated.", result.stdout)

        # Old splits deleted, 2 new splits added, committed
        # delete() comes from ExpenseSplit query mock; we can't assert exact call easily,
        # but commit and adds should have occurred:
        self.assertGreaterEqual(self.mock_db.add.call_count, 2)
        self.mock_db.commit.assert_called_once()

    def test_edit_split_sum_mismatch(self):
        """
        New splits do not sum to new amount -> error, Exit, no commit.
        """
        splits = [self._mk_split(self.mock_member1, 100)]
        member_lookup = {"Member1": self.mock_member1, "Member2": self.mock_member2}
        self._wire_edit_queries(existing_splits=splits, member_lookup=member_lookup)

        seq = [
            "Mismatch test",
            "200",  # New amount
            "2024-04-01",
            "Member1",  # Payer
            "Member1", "50",  # Splits sum = 50 + 100 = 150 != 200
            "Member2", "100",
            "",  # finish
        ]
        user_input = "\n".join(seq) + "\n"

        # Last requested name updates as prompts happen; set to last one here
        self._last_requested_member_name = "Member2"

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "edit", "123"], input=user_input)

        self.assertEqual(result.exit_code, 0)  # command exits via typer.Exit()
        self.assertIn("❌ Split amounts must sum to the expense amount.", result.stdout)
        self.mock_db.commit.assert_not_called()
        # No adds when mismatch
        self.mock_db.add.assert_not_called()

    def test_edit_invalid_amount(self):
        """Amount must be positive float -> invalid input exits early, no commit."""
        self._wire_edit_queries()

        seq = [
            "Keep desc",
            "-5",  # invalid
            "2024-01-02",  # won't be reached (but harmless)
            "Member1",
            "",  # finish
        ]
        user_input = "\n".join(seq) + "\n"
        self._last_requested_member_name = "Member1"

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "edit", "123"], input=user_input)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("❌ Amount must be a positive number.", result.stdout)
        self.mock_db.commit.assert_not_called()

    def test_edit_payer_not_found(self):
        """If new payer not in current group -> error, exit, no commit."""
        splits = [self._mk_split(self.mock_member1, 100)]
        self._wire_edit_queries(existing_splits=splits, payer_exists=True, member_lookup={"Ghost": None})

        seq = [
            "Pay change",
            "100",
            "2024-02-02",
            "Ghost",  # not found
            "",  # finish
        ]
        user_input = "\n".join(seq) + "\n"
        self._last_requested_member_name = "Ghost"

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "edit", "123"], input=user_input)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("❌ Payer 'Ghost' not found in the selected group.", result.stdout)
        self.mock_db.commit.assert_not_called()

    def test_edit_member_not_found_in_new_split(self):
        """If a new split references an unknown member -> exit and no commit."""
        splits = [self._mk_split(self.mock_member1, 100)]
        self._wire_edit_queries(existing_splits=splits,
                                member_lookup={"UnknownGuy": None, "Member1": self.mock_member1})

        seq = [
            "Desc",
            "100",
            "2024-05-05",
            "",  # We don't change the payer, this is already covered in another test
            "UnknownGuy", "50",  # split member not in group -> error
            "",  # finish (won't be reached)
        ]
        user_input = "\n".join(seq) + "\n"
        self._last_requested_member_name = "UnknownGuy"

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "edit", "123"], input=user_input)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("❌ Member 'UnknownGuy' not found in this group.", result.stdout)
        self.mock_db.commit.assert_not_called()
        self.mock_db.add.assert_not_called()

    def test_edit_expense_not_found(self):
        """If the expense does not exist in current group -> message and exit."""
        self._wire_edit_queries(expense_exists=False)

        with self.mock_db_and_group(module_path="app.commands.expense"):
            result = self.runner.invoke(app, ["expense", "edit", "999"], input="\n")

        self.assertEqual(result.exit_code, 0)
        self.assertIn("❌ Expense ID 999 not found in the current group.", result.stdout)
        self.mock_db.commit.assert_not_called()
