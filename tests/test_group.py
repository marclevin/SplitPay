import unittest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from tests.base import BaseCLITest
from cli import app

runner = CliRunner()

class TestGroupCommands(BaseCLITest):

    @patch('app.commands.group.set_active_group_id')
    def test_create(self, mock_set_active_group_id):
        # Test if we can create a new group, assuming the group doesn't exist
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mock_set_active_group_id.return_value = None
        result = runner.invoke(app, ["group", "create", "test_group"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("✅ Created group 'test_group'", result.stdout)

    @patch('app.commands.group.set_active_group_id')
    def test_create_existing(self, mock_set_active_group_id):
        # Test if we cannot create a group that already exists
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
        result = runner.invoke(app, ["group", "create", "existing_group"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("❌ Group 'existing_group' already exists.", result.stdout)






