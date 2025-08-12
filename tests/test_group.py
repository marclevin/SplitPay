from unittest.mock import patch, MagicMock

from cli import app
from tests.base import BaseCLITest


class TestGroupCommands(BaseCLITest):

    def setUp(self):
        super().setUp()

    # Command: group select
    @patch('app.commands.group.set_active_group_id')
    def test_select(self, mock_set_active_group_id):
        mock_set_active_group_id.return_value = None
        # Test if we can select a group
        self.mock_db.query.return_value.all.return_value = [
            MagicMock(name="Group1", id=1),
            MagicMock(name="Group2", id=2)
        ]
        with self.mock_db_and_group(module_path="app.commands.group"):
            result = self.runner.invoke(app, ["group", "select"], input="1\n")
            self.assertEqual(result.exit_code, 0)

    @patch('app.commands.group.set_active_group_id')
    def test_select_invalid(self, mock_set_active_group_id):
        mock_set_active_group_id.return_value = None
        # Test if we cannot select a group with an invalid number
        self.mock_db.query.return_value.all.return_value = [
            MagicMock(name="Group1", id=1),
            MagicMock(name="Group2", id=2)
        ]
        with self.mock_db_and_group(module_path="app.commands.group"):
            result = self.runner.invoke(app, ["group", "select"], input="3\n")
            self.assertEqual(result.exit_code, 0)
            self.assertIn("❌ Invalid selection.", result.stdout)

    # Command: group create
    @patch('app.commands.group.set_active_group_id')
    def test_create(self, mock_set_active_group_id):
        # Test if we can create a new group, assuming the group doesn't exist
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mock_set_active_group_id.return_value = None
        with self.mock_db_and_group(module_path="app.commands.group"):
            result = self.runner.invoke(app, ["group", "create", "test_group"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("✅ Created group 'test_group'", result.stdout)

    def test_create_existing(self):
        # Test if we cannot create a group that already exists
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
        with self.mock_db_and_group(module_path="app.commands.group"):
            result = self.runner.invoke(app, ["group", "create", "existing_group"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("❌ Group 'existing_group' already exists.", result.stdout)

    # Command: group delete
    @patch('app.commands.group.get_active_group_id')
    @patch('app.commands.group.clear_active_group')
    def test_delete(self, mock_clear_active_group, mock_get_active_group_id):
        # Test if we can delete a group, assuming the group exists and is active
        group = MagicMock()
        group.name = "test_group"
        group.id = 1
        mock_clear_active_group.return_value = None
        mock_get_active_group_id.return_value = group.id
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = group
        with self.mock_db_and_group(module_path="app.commands.group"):
            result = self.runner.invoke(app, ["group", "delete", "test_group"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("✅ Deleted group 'test_group'", result.stdout)

    def test_delete_nonexistent(self):
        # Test if we cannot delete a group that doesn't exist
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = None
        with self.mock_db_and_group(module_path="app.commands.group"):
            result = self.runner.invoke(app, ["group", "delete", "nonexistent_group"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("❌ Group 'nonexistent_group' not found.", result.stdout)

    # Command: group show
    def test_show(self):
        self.mock_db.query.return_value.all.return_value = [
            MagicMock(name="Group1", id=1),
            MagicMock(name="Group2", id=2)
        ]
        with self.mock_db_and_group(module_path="app.commands.group"):
            result = self.runner.invoke(app, ["group", "show"])
            self.assertEqual(result.exit_code, 0)

    def test_show_no_groups(self):
        self.mock_db.query.return_value.all.return_value = []
        with self.mock_db_and_group(module_path="app.commands.group"):
            result = self.runner.invoke(app, ["group", "show"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("❌ No groups found.", result.stdout)

    # Command: group current
    def test_current(self):
        # Test if we can show the current group, our base sets this, so we can just call it
        with self.mock_db_and_group(module_path="app.commands.group"):
            result = self.runner.invoke(app, ["group", "current"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("📁 Current group: 'TestGroup'", result.stdout)

    # Command: group clear-session
    @patch('app.commands.group.clear_active_group')
    def test_clear_session(self, mock_clear_active_group):
        # Test if we can clear the session
        mock_clear_active_group = MagicMock()
        mock_clear_active_group.return_value = None
        with self.mock_db_and_group(module_path="app.commands.group"):
            result = self.runner.invoke(app, ["group", "clear-session"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("🧹 Session cleared.", result.stdout)
