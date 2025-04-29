import json
import subprocess
import tempfile
from datetime import datetime, date

import typer
from sqlalchemy import func
from typing_extensions import Annotated
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Member, Group, Expense, ExpenseSplit, Payment

# Session Logic
import os

SESSION_FILE = ".eco_session"


def set_active_group(group_id: int):
    with open(SESSION_FILE, "w") as f:
        f.write(str(group_id))


def get_active_group_id():
    if not os.path.exists(SESSION_FILE):
        return None
    with open(SESSION_FILE, "r") as f:
        return int(f.read().strip())


def clear_active_group():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)


app = typer.Typer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.command()
def clear_session():
    """
    Clear the current group session.
    """
    clear_active_group()
    typer.echo("🧹 Session cleared.")


@app.command()
def select_group(name: str):
    """
    Select an active group session.
    """
    db: Session = next(get_db())
    group = db.query(Group).filter_by(name=name).first()
    if not group:
        typer.echo(f"❌ Group '{name}' not found.")
        raise typer.Exit()

    set_active_group(group.id)
    typer.echo(f"✅ Group '{name}' selected as active session.")


@app.command()
def add_member(name: str):
    """
    Add a new member to a group.
    """
    db: Session = next(get_db())
    group_id = get_active_group_id()
    if not group_id:
        typer.echo(f"❌ Select a group first.")
        raise typer.Exit()
    group = db.query(Group).filter_by(id=group_id).first()
    new_member = Member(name=name, group_id=group.id)
    db.add(new_member)
    db.commit()
    typer.echo(f"✅ Added member '{name}' to group '{group.name}'.")


@app.command()
def list_members(group_name: Annotated[str, typer.Option(help="Name of the group to list members from.")] = None):
    """
    List all members in a group.
    """
    db: Session = next(get_db())
    if group_name is None:
        group_id = get_active_group_id()
        if not group_id:
            typer.echo("❌ No active group session found.")
            raise typer.Exit()
        group_name = db.query(Group).filter_by(id=group_id).first().name
    group = db.query(Group).filter_by(name=group_name).first()
    if not group:
        typer.echo(f"❌ Group '{group_name}' not found.")
        raise typer.Exit()

    members = db.query(Member).filter_by(group_id=group.id).all()
    if not members:
        typer.echo("No members found in this group.")
        return

    typer.echo(f"👥 Members in '{group_name}':")
    for m in members:
        typer.echo(f"• {m.name} (ID: {m.id})")


@app.command()
def create_group(name: str):
    """
    Create a new group.
    """
    db: Session = next(get_db())

    existing = db.query(Group).filter_by(name=name).first()
    if existing:
        typer.echo(f"⚠️ Group '{name}' already exists.")
        raise typer.Exit()

    group = Group(name=name)
    db.add(group)
    db.commit()
    typer.echo(f"✅ Created group '{name}'.")


@app.command()
def current_group():
    """
    Show the currently selected group.
    """
    db: Session = next(get_db())
    group_id = get_active_group_id()
    if not group_id:
        typer.echo("⚠️ No group currently selected.")
        return

    group = db.query(Group).filter_by(id=group_id).first()
    if not group:
        typer.echo("⚠️ Selected group no longer exists.")
        clear_active_group()
        return

    typer.echo(f"📁 Current group: '{group.name}' (ID: {group.id})")


@app.command()
def list_groups():
    """
    List all groups.
    """
    db: Session = next(get_db())
    groups = db.query(Group).all()

    if not groups:
        typer.echo("No groups found.")
        return

    typer.echo("📁 Groups:")
    for g in groups:
        typer.echo(f"• {g.name} (ID: {g.id})")


@app.command()
def delete_group(name: str):
    """
    Delete a group by name.
    WARNING: This deletes all associated members, expenses, and payments.
    """
    db: Session = next(get_db())
    group = db.query(Group).filter_by(name=name).first()
    if not group:
        typer.echo(f"❌ Group '{name}' not found.")
        raise typer.Exit()
    if group.id == get_active_group_id():
        clear_active_group()
        typer.echo(f"⚠️ Cleared active group session as it was deleted.")
    db.delete(group)
    db.commit()
    typer.echo(f"🗑️ Deleted group '{name}'.")


# Expense Tracking


@app.command()
def add_expense(
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
    db: Session = next(get_db())
    group_id = get_active_group_id()
    if not group_id:
        typer.echo("⚠️ No group selected.")
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
        members.append(member)
        # Check if the member exists at all.
        member_obj = db.query(Member).filter(Member.name == member).first()
        if not member_obj:
            typer.echo(f"❌ Member '{member}' not found.")
            raise typer.Exit()

    payer = db.query(Member).filter(Member.name == paid_by, Member.group_id == group_id).first()
    if not payer:
        typer.echo(f"❌ Payer '{paid_by}' not found in the selected group.")
        raise typer.Exit()
    split_between = members if members else [payer.name]

    members = db.query(Member).filter(Member.name.in_(split_between), Member.group_id == group_id).all()
    if len(members) != len(split_between):
        typer.echo(f"❌ Some members in split not found. Found: {[m.name for m in members]}")
        raise typer.Exit()

    split_amount = round(amount / len(members), 2)

    expense = Expense(
        description=description,
        amount=amount,
        date=date_of_expense,
        paid_by_id=payer.id,
        group_id=group_id
    )
    db.add(expense)
    db.commit()

    for member in members:
        split = ExpenseSplit(
            expense_id=expense.id,
            member_id=member.id,
            share_amount=split_amount
        )
        db.add(split)

    db.commit()
    typer.echo(f"✅ Expense '{description}' added and split between {', '.join(split_between)}.")


@app.command()
def edit_expense(expense_id: int):
    """
    Edit an existing expense using prompts.
    """
    db: Session = next(get_db())
    expense = db.query(Expense).filter_by(id=expense_id).first()
    if not expense:
        typer.echo(f"❌ Expense ID {expense_id} not found.")
        raise typer.Exit()

    # Prompt for new values
    typer.echo(f"Editing expense ID {expense_id}:")
    typer.echo(f"Current description: {expense.description}")
    expense.description = typer.prompt("Description", default=expense.description)
    typer.echo(f"Current amount: {expense.amount}")
    expense.amount = typer.prompt("Amount", default=expense.amount)
    typer.echo(f"Current date: {expense.date}")
    expense.date = typer.prompt("Date (YYYY-MM-DD)", default=expense.date.strftime("%Y-%m-%d"))
    typer.echo(f"Current paid by: {expense.payer.name}")
    new_payer = typer.prompt("Paid by (member name)", default=expense.payer.name)
    payer = db.query(Member).filter_by(name=new_payer, group_id=expense.group_id).first()
    if not payer:
        typer.echo(f"❌ Payer '{new_payer}' not found in the selected group.")
        raise typer.Exit()
    expense.paid_by_id = payer.id
    typer.echo(f"Current splits: {', '.join([f'{s.member.name}: {s.share_amount}' for s in expense.splits])}")
    # Prompt for new splits
    splits = []
    while True:
        member_name = typer.prompt("Member name", "")
        if not member_name or member_name == "" or len(member_name) == 0:
            break
        share_amount = typer.prompt("Share amount", default=0.0)
        # Check if the member exists at all.
        member_obj = db.query(Member).filter(Member.name == str(member_name)).first()
        if not member_obj:
            typer.echo(f"❌ Member '{member_name}' not found.")
            raise typer.Exit()
        splits.append({"member_id": member_obj.id, "share_amount": share_amount})
    db.query(ExpenseSplit).filter_by(expense_id=expense.id).delete()

    for split in splits:
        new_split = ExpenseSplit(
            expense_id=expense.id,
            member_id=split["member_id"],
            share_amount=split["share_amount"]
        )
        db.add(new_split)

    db.commit()
    typer.echo(f"✅ Expense ID {expense_id} updated.")


@app.command()
def show_balances():
    """
    Calculate and display net balances for each member in the active group.
    """
    db: Session = next(get_db())
    group_id = get_active_group_id()
    if not group_id:
        typer.echo("⚠️ No group selected.")
        raise typer.Exit()

    members = db.query(Member).filter_by(group_id=group_id).all()
    if not members:
        typer.echo("⚠️ No members found in group.")
        return

    balances = {}

    for member in members:
        # Total amount the member paid
        total_paid = db.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(
            Expense.paid_by_id == member.id,
            Expense.group_id == group_id
        ).scalar()

        # Total amount the member owes (sum of their splits)
        total_owed = db.query(
            func.coalesce(func.sum(ExpenseSplit.share_amount), 0)
        ).join(Expense).filter(
            ExpenseSplit.member_id == member.id,
            Expense.group_id == group_id
        ).scalar()

        # Net balance
        # Sum of repayments made
        repayments_made = db.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).filter(
            Payment.from_id == member.id,
            Payment.group_id == group_id
        ).scalar()

        # Sum of repayments received
        repayments_received = db.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).filter(
            Payment.to_id == member.id,
            Payment.group_id == group_id
        ).scalar()

        # Net balance
        net_balance = round((total_paid + repayments_made) - (total_owed + repayments_received), 2)
        balances[member.name] = net_balance

    typer.echo("💸 Group Balances:")
    for name, balance in balances.items():
        if balance > 0:
            typer.echo(f"✅ {name} is owed R{balance}")
        elif balance < 0:
            typer.echo(f"❌ {name} owes R{abs(balance)}")
        else:
            typer.echo(f"⚖️ {name} is settled up.")

    typer.echo("\n🔁 Simplified Transactions:")
    transactions = simplify_debts(balances)
    if not transactions:
        typer.echo("Everyone is settled up!")
    for debtor, creditor, amount in transactions:
        typer.echo(f"➡️ {debtor} pays {creditor} R{amount}")



@app.command()
def record_payment(from_member: str, to_member: str, amount: float):
    """
    Record a repayment from one member to another.
    """
    db: Session = next(get_db())
    group_id = get_active_group_id()
    if not group_id:
        typer.echo("⚠️ No group selected.")
        raise typer.Exit()

    payer = db.query(Member).filter(Member.name == from_member, Member.group_id == group_id).first()
    recipient = db.query(Member).filter(Member.name == to_member, Member.group_id == group_id).first()

    if not payer or not recipient:
        typer.echo("❌ Members not found in this group.")
        raise typer.Exit()

    payment = Payment(
        from_id=payer.id,
        to_id=recipient.id,
        amount=amount,
        group_id=group_id
    )

    db.add(payment)
    db.commit()
    typer.echo(f"✅ Payment recorded: {from_member} paid {to_member} R{amount}.")


def simplify_debts(balances: dict[str, float]):
    creditors = []
    debtors = []

    for name, balance in balances.items():
        if balance > 0:
            creditors.append((name, balance))
        elif balance < 0:
            debtors.append((name, -balance))  # make positive

    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    transactions = []

    i, j = 0, 0

    while i < len(debtors) and j < len(creditors):
        debtor, debt_amt = debtors[i]
        creditor, credit_amt = creditors[j]

        settled_amt = min(debt_amt, credit_amt)

        transactions.append((debtor, creditor, settled_amt))

        debtors[i] = (debtor, debt_amt - settled_amt)
        creditors[j] = (creditor, credit_amt - settled_amt)

        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1

    return transactions


if __name__ == "__main__":
    app()
