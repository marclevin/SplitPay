import unittest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from tests.base import BaseCLITest
from cli import app

runner = CliRunner()


class TestGroupCommands(BaseCLITest):

    def setUp(self):
        super().setUp()

    # Command: group create
    @patch('app.commands.group.set_active_group_id')
    def test_create(self, mock_set_active_group_id):
        # Test if we can create a new group, assuming the group doesn't exist
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mock_set_active_group_id.return_value = None
        result = runner.invoke(app, ["group", "create", "test_group"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("✅ Created group 'test_group'", result.stdout)

    def test_create_existing(self):
        # Test if we cannot create a group that already exists
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
        result = runner.invoke(app, ["group", "create", "existing_group"])
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
        result = runner.invoke(app, ["group", "delete", "test_group"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("✅ Deleted group 'test_group'", result.stdout)

    def test_delete_nonexistent(self):
        # Test if we cannot delete a group that doesn't exist
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = None
        result = runner.invoke(app, ["group", "delete", "nonexistent_group"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("❌ Group 'nonexistent_group' not found.", result.stdout)

