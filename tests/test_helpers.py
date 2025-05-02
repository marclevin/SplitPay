# tests/test_helpers.py

from unittest.mock import patch, mock_open, MagicMock

import typer

from app.models import Group
from tests.base import BaseCLITest
from app.utils.helpers import (
    set_active_group_id,
    get_active_group_id,
    clear_active_group,
    get_db,
    get_db_and_group,
    resolve_or_prompt_group,
)


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
        self.patches["app.utils.helpers.get_active_group_id"].return_value = None
        with patch("app.utils.helpers.set_active_group_id") as mock_set_id:
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
        self.patches["app.utils.helpers.get_active_group_id"].return_value = None
        with patch("typer.prompt", return_value="2"), patch("app.utils.helpers.set_active_group_id") as mock_set_id:
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
        self.patches["app.utils.helpers.get_active_group_id"].return_value = None
        with patch("typer.prompt", return_value="x"):
            with self.assertRaises(typer.Exit):
                resolve_or_prompt_group(self.mock_db)
