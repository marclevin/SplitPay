# tests/base.py

import unittest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

class BaseCLITest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

        session_path = "app.utils.helpers.SessionLocal"
        self.session_patcher = patch(session_path)
        self.mock_session_local = self.session_patcher.start()

        # Create a fake DB session
        self.mock_db = MagicMock()
        self.mock_session_local.return_value = self.mock_db

        # Optional: stub commit/rollback if needed
        self.mock_db.commit.return_value = None
        self.mock_db.rollback.return_value = None

    def tearDown(self):
        self.session_patcher.stop()
