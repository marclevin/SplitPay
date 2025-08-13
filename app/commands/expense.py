from datetime import datetime

import typer
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from typing_extensions import Annotated

from app.models import Member, Expense, ExpenseSplit
from app.utils.helpers import get_db_and_group, console, money, date_str

expense_app = typer.Typer(no_args_is_help=True)


@expense_app.command()
def add(
        amount: Annotated[float, typer.Option(help="Amount of the expense.", prompt=True)],
        paid_by: Annotated[str, typer.Option(help="Name of the member who paid.", prompt=True)],
        description: Annotated[str, typer.Option(help="Description of the expense.", prompt=True)],
        date_of_expense: Annotated[
            datetime, typer.Option(help="Date of the expense (YYYY-MM-DD).", prompt=True)] = date_str(datetime.now()),
):
    """
    Add a new expense.
    """
    # Prompt the user for the members to split the expense with.
    with get_db_and_group() as (db, group):
        # Check if the payer exists in the current group
        if not isinstance(amount, (int, float)) or amount <= 0:
            typer.echo("❌ Amount must be a positive number.")
            raise typer.Exit()
        payer = db.query(Member).filter(Member.name == paid_by, Member.group_id == group.id).first()
        if not payer:
            typer.echo(f"❌ Payer '{paid_by}' not found in the selected group.")
            raise typer.Exit()
        members = []
        typer.echo("👥 Enter the name of a member this expense will be split with (Enter nothing to stop):")
        while True:
            member = typer.prompt("Member name", "")
            # Make sure member is a string and not empty
            if not isinstance(member, str) or not member.strip():
                break
            if not member or member == "" or len(member) == 0:
                break
            # Check if the member exists at all.
            member_obj = db.query(Member).filter(Member.name == member).first()
            # Now check if the member is the payer, we don't want to add the payer to the split list.
            if member_obj and member_obj.id == payer.id:
                typer.echo("❌ Payer cannot be included in the split list.")
                continue
            if not member_obj:
                typer.echo(f"❌ Member '{member}' not found, please add them first.")
                continue
            # If the member exists, add them to the list.
            members.append(member)

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


@expense_app.command()
def edit(expense_id: int):
    """
    Edit an existing expense using interactive prompts.

    Notes:
    - The expense must belong to the currently active group.
    - If you enter no new splits, the existing splits are preserved.
    - If you enter new splits, their amounts must sum exactly to the expense amount.
    """
    # Use the same context manager pattern as other commands
    with get_db_and_group() as (db, group):
        # Fetch the expense scoped to the active group
        expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.group_id == group.id
        ).first()

        if not expense:
            typer.echo(f"❌ Expense ID {expense_id} not found in the current group.")
            raise typer.Exit()

        # Resolve current payer (avoid assuming a relationship property exists)
        current_payer = db.query(Member).filter_by(id=expense.paid_by_id).first()
        current_payer_name = current_payer.name if current_payer else "Unknown"

        # --- Prompt for main expense fields ---
        typer.echo(f"🛠️ Editing expense ID {expense_id} in group '{group.name}'")

        # Description
        typer.echo(f"Current description: {expense.description}")
        new_description = typer.prompt("Description", default=expense.description)

        # Amount (ensure float)
        typer.echo(f"Current amount: {expense.amount}")
        new_amount_str = str(typer.prompt("Amount", default=str(expense.amount)))
        try:
            new_amount = float(new_amount_str)
            if new_amount <= 0:
                raise ValueError
        except ValueError:
            typer.echo("❌ Amount must be a positive number.")
            raise typer.Exit()

        # Date (accept YYYY-MM-DD)
        typer.echo(
            f"Current date: {date_str(expense.date)}")
        new_date_input = typer.prompt("Date (YYYY-MM-DD)",
                                      default=date_str(expense.date))
        try:
            new_date = datetime.fromisoformat(new_date_input)
        except ValueError:
            typer.echo("❌ Invalid date format. Use YYYY-MM-DD.")
            raise typer.Exit()

        # Payer (must exist in current group)
        typer.echo(f"Current paid by: {current_payer_name}")
        new_payer_name = typer.prompt("Paid by (member name)", default=current_payer_name).strip()
        # If we haven't changed the payer, we can skip this check
        if new_payer_name != current_payer_name:
            payer = db.query(Member).filter(
                Member.name == new_payer_name,
                Member.group_id == group.id
            ).first()
        else:
            # If we are keeping the same payer, just use the current one
            payer = current_payer
        if not payer:
            typer.echo(f"❌ Payer '{new_payer_name}' not found in the selected group.")
            raise typer.Exit()

        # --- Show current splits ---
        existing_splits = db.query(ExpenseSplit).filter_by(expense_id=expense.id).all()
        if existing_splits:
            split_preview = ", ".join(
                [f"{db.query(Member).filter_by(id=s.member_id).first().name}: {s.share_amount}" for s in
                 existing_splits])
            typer.echo(f"Current splits: {split_preview}")
        else:
            typer.echo("Current splits: <none>")

        # --- Prompt for new splits (optional) ---
        typer.echo("Enter new splits (leave member name empty to finish).")
        typer.echo("If you leave this section empty, existing splits will be kept.")
        new_splits_input: list[dict] = []

        while True:
            member_name = typer.prompt("Member name", default="").strip()
            if not member_name:
                break

            # Validate member is in the current group
            member_obj = db.query(Member).filter(
                Member.name == member_name,
                Member.group_id == group.id
            ).first()
            if not member_obj:
                typer.echo(f"❌ Member '{member_name}' not found in this group.")
                raise typer.Exit()

            share_str = str(typer.prompt("Share amount", default="0"))
            try:
                share_amount = float(share_str)
                if share_amount < 0:
                    raise ValueError
            except ValueError:
                typer.echo("❌ Share amount must be a non-negative number.")
                raise typer.Exit()

            new_splits_input.append(
                {"member_id": member_obj.id, "member_name": member_obj.name, "share_amount": round(share_amount, 2)})

        # --- Apply edits ---
        expense.description = new_description
        expense.amount = round(new_amount, 2)
        expense.date = new_date
        expense.paid_by_id = payer.id

        # If user entered any new splits, replace existing ones (with validation)
        if new_splits_input:
            total_new_splits = round(sum(s["share_amount"] for s in new_splits_input), 2)
            if total_new_splits != expense.amount:
                typer.echo(
                    f"❌ Split amounts must sum to the expense amount. "
                    f"Sum of splits = {total_new_splits}, expense amount = {expense.amount}."
                )
                raise typer.Exit()

            # Remove old splits for this expense
            db.query(ExpenseSplit).filter_by(expense_id=expense.id).delete()

            # Add the new splits
            for s in new_splits_input:
                db.add(ExpenseSplit(
                    expense_id=expense.id,
                    member_id=s["member_id"],
                    share_amount=s["share_amount"]
                ))
        else:
            # No new splits provided → keep existing splits as-is
            # (Optional) You can still sanity-check existing splits against new amount:
            existing_total = round(sum(s.share_amount for s in existing_splits), 2)
            if existing_splits and existing_total != expense.amount:
                typer.echo(
                    f"⚠️ Warning: Existing splits (R{existing_total}) do not sum to the new amount (R{expense.amount}).\n"
                    f"Keeping existing splits. Consider re-running edit to update splits."
                )

        # Commit all changes atomically at the end
        db.commit()

        # Success message
        payer_name_display = db.query(Member).filter_by(
            id=expense.paid_by_id).first().name if expense.paid_by_id else "Unknown"
        typer.echo(
            f"✅ Expense ID {expense_id} updated. ({expense.description}, R{expense.amount}, paid by {payer_name_display} on {date_str(expense.date)})")


@expense_app.command()
def show():
    """
    Show all expenses in the current group, rendered as high-quality Rich panels.
    """
    with get_db_and_group() as (db, group):
        expenses = (
            db.query(Expense)
            .filter_by(group_id=group.id)
            .order_by(Expense.date.desc(), Expense.id.desc())
            .all()
        )
        if not expenses:
            console.print(Panel("No expenses found in the current group.", title="📊 Expenses", box=box.ROUNDED))
            raise typer.Exit()

        console.print(f"[bold]📊 Expenses in group '{group.name}':[/]\n")
        for expense in expenses:
            # payer
            payer = expense.payer

            # splits
            splits = expense.splits

            # Header row (title + amount)
            header = Table.grid(expand=True)
            header.add_column(justify="left", ratio=3)
            header.add_column(justify="right", ratio=1)

            title_left = (
                f"[b]{expense.description}[/]\n"
                f"[dim]ID #{expense.id} • {date_str(expense.date)}[/dim]"
            )
            header.add_row(title_left, f"[b]{money(-expense.amount)}[/b]")

            # Payer line
            payer_line = Table.grid()
            payer_line.add_column()
            payer_name = payer.name if payer else "Unknown"
            payer_line.add_row(
                f"Paid by: [bold {payer.color}]{payer_name}[/]"
            )

            # Splits table
            splits_table = Table(box=box.SIMPLE_HEAVY, expand=True, show_edge=True)
            splits_table.add_column("Member", style="bold", ratio=3)
            splits_table.add_column("Share", justify="right", ratio=1)

            total_shares = 0.0
            for s in splits:
                mname = s.member.name if s.member else "Unknown"
                mcolor = s.member.color if s.member else "white"
                splits_table.add_row(
                    f"[{mcolor}]{mname}[/]",
                    money(float(s.share_amount or 0.0)),
                )
                total_shares += float(s.share_amount or 0.0)

            # Footer / consistency note
            footer = Table.grid(expand=True)
            footer.add_column(justify="left", ratio=3)
            footer.add_column(justify="right", ratio=1)
            # Compare split total to expense amount
            delta = round((total_shares or 0.0) - float(expense.amount or 0.0), 2)
            if abs(delta) < 0.01:
                footer.add_row("[dim]Splits total[/dim]", f"[dim]{money(total_shares)}[/dim]")
            else:
                # highlight mismatch
                footer.add_row(
                    "[yellow]⚠ Splits total (mismatch)[/]",
                    f"[yellow]{money(total_shares)}[/]",
                )

            # Assemble the card
            card = Panel(
                Group(header, payer_line, splits_table, footer),
                box=box.ROUNDED,
                padding=(1, 2),
            )

            console.print(card)


@expense_app.command()
def delete(
        expense_id: int,
        yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation and delete immediately.")] = False,
):
    """
    Delete an expense and its associated splits.

    Behavior:
    - Validates the expense belongs to the active group.
    - Asks for confirmation unless --yes/-y is provided.
    - Deletes all ExpenseSplit rows for the expense first, then the Expense.
    """
    with get_db_and_group() as (db, group):
        # Fetch the expense scoped to the active group
        expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.group_id == group.id
        ).first()

        if not expense:
            typer.echo(f"❌ Expense ID {expense_id} not found in the current group.")
            raise typer.Exit()

        # Fetch some context for a helpful prompt/message
        payer = db.query(Member).filter_by(id=expense.paid_by_id).first()
        payer_name = payer.name if payer else "Unknown"
        date_expense = date_str(expense.date)

        # Confirmation (unless --yes given)
        if not yes:
            typer.echo(f"🗑️ You are about to delete:")
            typer.echo(f"   • ID: {expense.id}")
            typer.echo(f"   • Description: {expense.description}")
            typer.echo(f"   • Amount: R{expense.amount}")
            typer.echo(f"   • Paid by: {payer_name} on {date_expense}")
            if not typer.confirm("Proceed with deletion?"):
                typer.echo("❌ Deletion cancelled.")
                raise typer.Exit()

        try:
            # Delete splits first (robust even without FK cascade rules)
            splits_deleted = db.query(ExpenseSplit).filter_by(expense_id=expense.id).delete(synchronize_session=False)

            # Delete the expense itself
            db.delete(expense)

            # Commit atomically
            db.commit()

            typer.echo(f"✅ Deleted expense ID {expense_id} ('{expense.description}') and {splits_deleted} split(s).")
        except Exception as e:
            # Roll back on any failure to avoid partial deletes
            db.rollback()
            typer.echo(f"❌ Failed to delete expense ID {expense_id}: {e}")
            raise typer.Exit(code=1)
