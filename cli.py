import typer

from app.commands.group import group_app
from app.commands.member import member_app
from app.commands.expense import expense_app
from app.commands.splits import split_app


app = typer.Typer(no_args_is_help=True)
app.add_typer(group_app, name="group", help="Group management commands.")
app.add_typer(member_app, name="member", help="Member management commands.")
app.add_typer(expense_app, name="expense", help="Expense management commands.")
app.add_typer(split_app, name="split", help="Split management commands.")


if __name__ == "__main__":
    app()
