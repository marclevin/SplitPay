# tests/base.py

import unittest
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from app.models import Group


class BaseCLITest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

        # Patches
        self.patches = {}

        # Patch database session
        self._patch("app.utils.helpers.SessionLocal", new_callable=MagicMock)
        self.mock_db = self.patches["app.utils.helpers.SessionLocal"].start().return_value

        # Patch resolve_or_prompt_group
        self._patch("app.utils.helpers.resolve_or_prompt_group", return_value=1)

        # Patch session file handlers
        self._patch("builtins.open", new_callable=MagicMock)
        self._patch("os.path.exists", return_value=True)
        self._patch("os.remove")

        # Patch commonly used helper functions for easy access
        self._patch("app.utils.helpers.set_active_group_id")
        self._patch("app.utils.helpers.clear_active_group")
        self._patch("app.utils.helpers.get_active_group_id", return_value=1)

        # Fake group object
        self.mock_group = MagicMock(spec=Group)
        self.mock_group.id = 1
        self.mock_group.name = "TestGroup"

        # Default DB query behavior
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = self.mock_group
        self.mock_db.query.return_value.all.return_value = [self.mock_group]
        self.mock_db.commit.return_value = None
        self.mock_db.rollback.return_value = None

    def _patch(self, target, **kwargs):
        patcher = patch(target, **kwargs)
        mocked = patcher.start()
        self.patches[target] = patcher  # Store the patcher object instead of the mocked instance
        return mocked  # Return the mocked instance for immediate use if needed

    @contextmanager
    def mock_db_and_group(self, module_path="app.commands"):
        """Helper context manager to mock get_db_and_group for any command module.
        
        Args:
            module_path (str): The module path where get_db_and_group is imported from.
                              Defaults to "app.commands" but can be overridden for different modules.
        """
        with patch(f'{module_path}.get_db_and_group') as mock_get_db_and_group:
            mock_get_db_and_group.return_value.__enter__.return_value = (self.mock_db, self.mock_group)
            yield mock_get_db_and_group

    def tearDown(self):
        for patcher in self.patches.values():
            patcher.stop()  # Stop each patcher individually
        self.patches.clear()
