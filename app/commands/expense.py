import typer
from datetime import datetime
from typing_extensions import Annotated
from app.models import Member, Expense, ExpenseSplit
from app.commands.group import get_db_and_group
import random

expense_app = typer.Typer(no_args_is_help=True)

# List of colors for member names
MEMBER_COLORS = [
    "bright_blue",
    "bright_green",
    "bright_magenta",
    "bright_yellow",
    "bright_cyan",
    "bright_red",
    "green",
    "yellow",
    "blue",
    "magenta"
]


@expense_app.command()
def add(
        amount: Annotated[float, typer.Option(help="Amount of the expense.", prompt=True)],
        paid_by: Annotated[str, typer.Option(help="Name of the member who paid.", prompt=True)],
        description: Annotated[str, typer.Option(help="Description of the expense.", prompt=True)],
        date_of_expense: Annotated[
            datetime, typer.Option(help="Date of the expense (YYYY-MM-DD).", prompt=True)] = datetime.now(),
):
    """
    Add a new expense.
    """
    # Prompt the user for the members to split the expense with.
    with get_db_and_group() as (db, group):
        members = []
        typer.echo("👥 Enter the name of a member this expense will be split with (Enter nothing to stop):")
        while True:
            member = typer.prompt("Member name", "")
            # Make sure member is a string and not empty
            if not isinstance(member, str) or not member.strip():
                break
            if not member or member == "" or len(member) == 0:
                break
            members.append(member)
            # Check if the member exists at all.
            member_obj = db.query(Member).filter(Member.name == member).first()
            if not member_obj:
                typer.echo(f"❌ Member '{member}' not found.")
                raise typer.Exit()

        payer = db.query(Member).filter(Member.name == paid_by, Member.group_id == group.id).first()
        if not payer:
            typer.echo(f"❌ Payer '{paid_by}' not found in the selected group.")
            raise typer.Exit()
        split_between = members if members else [payer.name]

        members = db.query(Member).filter(Member.name.in_(split_between), Member.group_id == group.id).all()
        if len(members) != len(split_between):
            typer.echo(f"❌ Some members in split not found. Found: {[m.name for m in members]}")
            raise typer.Exit()

        split_amount = round(amount / len(members), 2)

        expense = Expense(
            description=description,
            amount=amount,
            date=date_of_expense,
            paid_by_id=payer.id,
            group_id=group.id
        )
        db.add(expense)
        # Must commit before adding splits to avoid foreign key constraint errors
        db.commit()

        for member in members:
            split = ExpenseSplit(
                expense_id=expense.id,
                member_id=member.id,
                share_amount=split_amount
            )
            db.add(split)

    typer.echo(f"✅ Expense '{description}' added and split between {', '.join(split_between)}.")


# @expense_app.command()
# def edit(expense_id: int):
#     """
#     Edit an existing expense using prompts.
#     """
#     db: Session = next(get_db())
#     expense = db.query(Expense).filter_by(id=expense_id).first()
#     if not expense:
#         typer.echo(f"❌ Expense ID {expense_id} not found.")
#         raise typer.Exit()

#     # Prompt for new values
#     typer.echo(f"Editing expense ID {expense_id}:")
#     typer.echo(f"Current description: {expense.description}")
#     expense.description = typer.prompt("Description", default=expense.description)
#     typer.echo(f"Current amount: {expense.amount}")
#     expense.amount = typer.prompt("Amount", default=expense.amount)
#     typer.echo(f"Current date: {expense.date}")
#     expense.date = typer.prompt("Date (YYYY-MM-DD)", default=expense.date.strftime("%Y-%m-%d"))
#     typer.echo(f"Current paid by: {expense.payer.name}")
#     new_payer = typer.prompt("Paid by (member name)", default=expense.payer.name)
#     payer = db.query(Member).filter_by(name=new_payer, group_id=expense.group_id).first()
#     if not payer:
#         typer.echo(f"❌ Payer '{new_payer}' not found in the selected group.")
#         raise typer.Exit()
#     expense.paid_by_id = payer.id
#     typer.echo(f"Current splits: {', '.join([f'{s.member.name}: {s.share_amount}' for s in expense.splits])}")
#     # Prompt for new splits
#     splits = []
#     while True:
#         member_name = typer.prompt("Member name", "")
#         if not member_name or member_name == "" or len(member_name) == 0:
#             break
#         share_amount = typer.prompt("Share amount", default=0.0)
#         # Check if the member exists at all.
#         member_obj = db.query(Member).filter(Member.name == str(member_name)).first()
#         if not member_obj:
#             typer.echo(f"❌ Member '{member_name}' not found.")
#             raise typer.Exit()
#         splits.append({"member_id": member_obj.id, "share_amount": share_amount})
#     db.query(ExpenseSplit).filter_by(expense_id=expense.id).delete()

#     for split in splits:
#         new_split = ExpenseSplit(
#             expense_id=expense.id,
#             member_id=split["member_id"],
#             share_amount=split["share_amount"]
#         )
#         db.add(new_split)

#     db.commit()
#     typer.echo(f"✅ Expense ID {expense_id} updated.")

@expense_app.command()
def show():
    """
    Show all expenses in the current group.
    """
    with get_db_and_group() as (db, group):
        expenses = db.query(Expense).filter_by(group_id=group.id).all()
        if not expenses:
            typer.echo("No expenses found in the current group.")
            raise typer.Exit()
        typer.echo(f"📊 Expenses in group '{group.name}':")
        
        # Create a mapping of member names to colors
        member_colors = {}
        for expense in expenses:
            splits = db.query(ExpenseSplit).filter_by(expense_id=expense.id).all()
            for split in splits:
                if split.member.name not in member_colors:
                    member_colors[split.member.name] = random.choice(MEMBER_COLORS)
        
        for expense in expenses:
            payer = db.query(Member).filter_by(id=expense.paid_by_id).first()
            splits = db.query(ExpenseSplit).filter_by(expense_id=expense.id).all()
            
            # Create colored split details
            split_details = []
            for split in splits:
                colored_name = typer.style(split.member.name, fg=member_colors[split.member.name])
                split_details.append(f"{colored_name}: {split.share_amount}")
            
            split_details_str = ", ".join(split_details)
            typer.echo(
                f"💰 {expense.description} - Amount: {expense.amount}, Paid by: {typer.style(payer.name, fg=member_colors[payer.name])}, Splits: {split_details_str}")
