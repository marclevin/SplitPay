from unittest.mock import MagicMock, patch

from tests.base import BaseCLITest
from app.commands.splits import split_app


class TestSplits(BaseCLITest):
    def test_show_no_members(self):
        """Test the `show` command when no members exist in the group."""
        with self.mock_db_and_group("app.commands.splits"):
            self.mock_db.query.return_value.filter_by.return_value.all.return_value = []  # No members
            result = self.runner.invoke(split_app, ["show"])
            self.assertEqual(result.exit_code, 0)

    def test_show_with_members(self):
        """Test the `show` command with members and balances."""
        with self.mock_db_and_group("app.commands.splits"):
            # Mock members
            mock_member = MagicMock()
            mock_member.id = 1
            mock_member.name = "Alice"

            self.mock_db.query.return_value.filter_by.return_value.all.return_value = [mock_member]

            # Return values for scalar() calls:
            # total_paid -> filter().scalar()
            # total_owed -> join().filter().scalar()
            # repaid     -> filter().scalar()
            # received   -> filter().scalar()

            # For the three plain filter().scalar() calls:
            self.mock_db.query.return_value.filter.return_value.scalar.side_effect = [100, 100, 100]

            # For the one join().filter().scalar() call:
            self.mock_db.query.return_value.join.return_value.filter.return_value.scalar.return_value = 100

            # Mock settlements, notice we use Alice paying herself since we don't need to mock another member
            with patch("app.utils.helpers.min_cash_flow_settlements", return_value=[("Alice", "Alice", 30.0)]):
                result = self.runner.invoke(split_app, ["show"])
                self.assertEqual(result.exit_code, 0)

    def test_payment_success(self):
        """Test the `payment` command when members exist and payment is recorded successfully."""
        with self.mock_db_and_group("app.commands.splits"):
            # Mock payer and recipient
            mock_payer = MagicMock()
            mock_payer.id = 1
            mock_payer.name = "Alice"
            mock_recipient = MagicMock()
            mock_recipient.id = 2
            mock_recipient.name = "Bob"

            self.mock_db.query.return_value.filter.return_value.first.side_effect = [mock_payer, mock_recipient]

            result = self.runner.invoke(split_app, ["payment", "Alice", "Bob", "50.0"])
            self.assertEqual(result.exit_code, 0)

    def test_payment_member_not_found(self):
        """Test the `payment` command when one or both members are not found."""
        with self.mock_db_and_group("app.commands.splits"):
            # Mock missing members
            self.mock_db.query.return_value.filter.return_value.first.return_value = None
            result = self.runner.invoke(split_app, ["payment", "Alice", "Bob", "50.0"])
            # We expect an exit code of 0 even if members are not found, as per the command's design
            self.assertEqual(result.exit_code, 0)
