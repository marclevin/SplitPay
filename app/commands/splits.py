import typer
from sqlalchemy import func

from app.models import Member, Expense, ExpenseSplit, Payment
from app.utils.helpers import get_db_and_group
split_app = typer.Typer(no_args_is_help=True)


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

            rows.append((m.name, total_paid, total_owed, repaid, received, net))

        # Stable ordering for display
        rows.sort(key=lambda r: r[0].lower())

        # Pretty print table
        def money(x: float) -> str:
            return f"R{round(x + 1e-9, 2):,.2f}"

        # Compute column widths
        headers = ["Member", "Paid", "Owed", "Repaid", "Received", "Net"]
        str_rows = [
            [name, money(paid), money(owed), money(repaid), money(received), money(net)]
            for (name, paid, owed, repaid, received, net) in rows
        ]
        col_widths = [max(len(h), *(len(r[i]) for r in str_rows)) for i, h in enumerate(headers)]

        def fmt_line(cells):
            return "  ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(cells))

        typer.echo(f"💸 Group Balances for '{group.name}':")
        typer.echo(fmt_line(headers))
        typer.echo(fmt_line(["-" * w for w in col_widths]))
        for r in str_rows:
            typer.echo(fmt_line(r))

        # Build balances dict for settlement (name -> net rounded to cents)
        balances = {name: round(net + 1e-9, 2) for (name, _, _, _, _, net) in rows}

        # Summary hints
        total_positive = round(sum(v for v in balances.values() if v > 0), 2)
        total_negative = round(sum(-v for v in balances.values() if v < 0), 2)
        typer.echo(f"\nΣ owed to creditors: {money(total_positive)} | Σ owed by debtors: {money(total_negative)}")

        # Compute minimal set of payments to settle up
        settlements = _min_cash_flow_settlements(balances)

        typer.echo("\n🔁 Suggested Settlements:")
        if not settlements:
            typer.echo("Everyone is settled up! 🎉")
        else:
            for debtor, creditor, amount in settlements:
                typer.echo(f"➡️  {debtor} pays {creditor} {money(amount)}")


def _min_cash_flow_settlements(balances: dict[str, float]) -> list[tuple[str, str, float]]:
    """
    Minimal-cash-flow settlement:
    - Repeatedly match the most negative (largest debtor) with the most positive (largest creditor).
    - Transfer the min(abs(debt), credit); update balances; continue until all ~0.
    This yields few, high-value transfers and is stable with rounding.
    """
    # Copy and clean tiny residuals
    eps = 0.01  # cents
    b = {k: (0.0 if abs(v) < eps else round(v, 2)) for k, v in balances.items()}
    creditors = [(k, v) for k, v in b.items() if v > 0]
    debtors = [(k, -v) for k, v in b.items() if v < 0]  # store as positive amounts

    # Nothing to do?
    if not creditors or not debtors:
        return []

    # Work on mutables
    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    i, j = 0, 0
    res: list[tuple[str, str, float]] = []

    while i < len(debtors) and j < len(creditors):
        d_name, d_amt = debtors[i]
        c_name, c_amt = creditors[j]

        pay = round(min(d_amt, c_amt), 2)
        if pay >= eps:
            res.append((d_name, c_name, pay))

        # Update remaining
        d_rem = round(d_amt - pay, 2)
        c_rem = round(c_amt - pay, 2)

        debtors[i] = (d_name, d_rem)
        creditors[j] = (c_name, c_rem)

        # Advance pointers when side is cleared (within epsilon)
        if d_rem <= eps:
            i += 1
        if c_rem <= eps:
            j += 1

    return res

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
