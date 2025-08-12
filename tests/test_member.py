from unittest.mock import MagicMock

from app.models import Member
from cli import app
from tests.base import BaseCLITest


class TestMemberCommands(BaseCLITest):
    def setUp(self):
        super().setUp()
        # Create a mock member for testing
        self.mock_member = MagicMock(spec=Member)
        self.mock_member.id = 1
        self.mock_member.name = "TestMember"
        self.mock_member.group_id = self.mock_group.id

    # Command: member add
    def test_add(self):
        """Test adding a new member to a group"""
        # Mock that the member doesn't exist yet
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = None
        with self.mock_db_and_group(module_path="app.commands.member"):
            result = self.runner.invoke(app, ["member", "add", "NewMember"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("✅ Added member 'NewMember' to group 'TestGroup'", result.stdout)

    def test_add_existing(self):
        """Test adding a member that already exists"""
        # Mock that the member already exists
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = self.mock_member
        with self.mock_db_and_group(module_path="app.commands.member"):
            result = self.runner.invoke(app, ["member", "add", "TestMember"])
            self.assertEqual(result.exit_code, 0)
            # Note: The command doesn't check for existing members, so it will add them anyway

    # Command: member show
    def test_show(self):
        """Test showing members in the current group"""
        self.mock_db.query.return_value.filter_by.return_value.all.return_value = [self.mock_member]
        with self.mock_db_and_group(module_path="app.commands.member"):
            result = self.runner.invoke(app, ["member", "show"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("👥 Members in 'TestGroup'", result.stdout)
            self.assertIn("• TestMember (ID: 1)", result.stdout)

    def test_show_specific_group(self):
        """Test showing members in a specific group"""
        other_group = MagicMock()
        other_group.id = 2
        other_group.name = "OtherGroup"
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = other_group
        self.mock_db.query.return_value.filter_by.return_value.all.return_value = [self.mock_member]

        with self.mock_db_and_group(module_path="app.commands.member"):
            result = self.runner.invoke(app, ["member", "show", "--group-name", "OtherGroup"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("👥 Members in 'OtherGroup'", result.stdout)

    def test_show_no_members(self):
        """Test showing members when there are none"""
        self.mock_db.query.return_value.filter_by.return_value.all.return_value = []
        with self.mock_db_and_group(module_path="app.commands.member"):
            result = self.runner.invoke(app, ["member", "show"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("No members found in this group", result.stdout)

    # Command: member delete
    def test_delete(self):
        """Test deleting an existing member"""
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = self.mock_member
        with self.mock_db_and_group(module_path="app.commands.member"):
            result = self.runner.invoke(app, ["member", "delete", "TestMember"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("✅ Deleted member 'TestMember' from group 'TestGroup'", result.stdout)

    def test_delete_nonexistent(self):
        """Test deleting a member that doesn't exist"""
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = None
        with self.mock_db_and_group(module_path="app.commands.member"):
            result = self.runner.invoke(app, ["member", "delete", "NonexistentMember"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("❌ Member 'NonexistentMember' not found in group 'TestGroup'", result.stdout)
