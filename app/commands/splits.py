import random

import typer
from sqlalchemy import func

from app.models import Member, Expense, ExpenseSplit, Payment
from app.utils.helpers import get_db_and_group, MEMBER_COLORS, money, console, min_cash_flow_settlements

split_app = typer.Typer(no_args_is_help=True)

from rich.table import Table


@split_app.command()
def show():
    """
    Calculate and display net balances and simplified settlements for the active group.
    """
    with get_db_and_group() as (db, group):
        members = db.query(Member).filter_by(group_id=group.id).all()
        if not members:
            typer.echo("⚠️ No members found in group.")
            return

        # Collect per-member tallies
        rows = []  # [(name, paid, owed, repaid, received, net)]

        for m in members:
            total_paid = db.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(
                Expense.paid_by_id == int(m.id),
                Expense.group_id == group.id
            ).scalar() or 0.0

            total_owed = db.query(func.coalesce(func.sum(ExpenseSplit.share_amount), 0.0)).join(Expense).filter(
                ExpenseSplit.member_id == int(m.id),
                Expense.group_id == group.id
            ).scalar() or 0.0

            repaid = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
                Payment.from_id == int(m.id),
                Payment.group_id == group.id
            ).scalar() or 0.0

            received = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
                Payment.to_id == int(m.id),
                Payment.group_id == group.id
            ).scalar() or 0.0

            # Net = what you're effectively up/down after expenses and repayments
            # Positive => others owe you; Negative => you owe others
            net = (total_paid + repaid) - (total_owed + received)

            rows.append((m.name, m.color, total_paid, total_owed, repaid, received, net))

        # Stable ordering for display
        rows.sort(key=lambda r: r[0].lower())

        # Create a Rich table
        table = Table(title=f"💸 Group Balances for '{group.name}'")
        table.add_column("Member", style="bold")
        table.add_column("Paid", justify="right")
        table.add_column("Owed", justify="right")
        table.add_column("Repaid", justify="right")
        table.add_column("Received", justify="right")
        table.add_column("Net", justify="right")

        for name, color, paid, owed, repaid, received, net in rows:
            table.add_row(
                f"[{color}]{name}[/{color}]",
                money(paid),
                money(owed),
                money(repaid),
                money(received),
                money(net),
            )

        console.print(table)

        # Build balances dict for settlement (name -> net rounded to cents)
        balances = {name: round(net + 1e-9, 2) for (name, _, _, _, _, _, net) in rows}
        # Create a color mapping for members, from their colors for the balances
        member_color_map = {name: color for (name, color, _, _, _, _, _,) in rows}

        # Summary hints
        total_positive = round(sum(v for v in balances.values() if v > 0), 2)
        total_negative = round(sum(-v for v in balances.values() if v < 0), 2)
        console.print(f"\nΣ owed to creditors: {money(total_positive)} | Σ owed by debtors: {money(-total_negative)}")

        # Compute minimal set of payments to settle up
        settlements = min_cash_flow_settlements(balances)

        console.print("\n🔁 Suggested Settlements:")
        if not settlements:
            console.print("Everyone is settled up! 🎉")
        else:
            for debtor, creditor, amount in settlements:
                console.print(
                    f"➡️  [{member_color_map[debtor]}]{debtor}[/{member_color_map[debtor]}] pays "
                    f"[{member_color_map[creditor]}]{creditor}[/{member_color_map[creditor]}] {money(amount)}"
                )


@split_app.command()
def payment(from_member: str, to_member: str, amount: float):
    """
    Record a repayment from one member to another.
    """
    with get_db_and_group() as (db, group):
        payer = db.query(Member).filter(Member.name == from_member, Member.group_id == group.id).first()
        recipient = db.query(Member).filter(Member.name == to_member, Member.group_id == group.id).first()

        if not payer or not recipient:
            typer.echo("❌ Members not found in this group.")
            raise typer.Exit()

        _payment = Payment(
            from_id=payer.id,
            to_id=recipient.id,
            amount=amount,
            group_id=group.id
        )

        db.add(_payment)
        typer.echo(f"✅ Payment recorded: {from_member} paid {to_member} R{amount}.")
