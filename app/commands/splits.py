import typer
from sqlalchemy import func

from app.commands.group import get_db_and_group
from app.models import Member, Expense, ExpenseSplit, Payment

split_app = typer.Typer(no_args_is_help=True)


@split_app.command()
def show():
    """
    Calculate and display net balances for each member in the active group.
    """
    with get_db_and_group() as (db, group):
        members = db.query(Member).filter_by(group_id=group.id).all()
        if not members:
            typer.echo("⚠️ No members found in group.")
            return

        balances = {}

        for member in members:
            # Total amount the member paid
            total_paid = db.query(
                func.coalesce(func.sum(Expense.amount), 0)
            ).filter(
                Expense.paid_by_id == int(member.id),
                Expense.group_id == group.id
            ).scalar()

            # Total amount the member owes (sum of their splits)
            total_owed = db.query(
                func.coalesce(func.sum(ExpenseSplit.share_amount), 0)
            ).join(Expense).filter(
                ExpenseSplit.member_id == int(member.id),
                Expense.group_id == group.id
            ).scalar()

            # Net balance
            # Sum of repayments made
            repayments_made = db.query(
                func.coalesce(func.sum(Payment.amount), 0)
            ).filter(
                Payment.from_id == int(member.id),
                Payment.group_id == group.id
            ).scalar()

            # Sum of repayments received
            repayments_received = db.query(
                func.coalesce(func.sum(Payment.amount), 0)
            ).filter(
                Payment.to_id == int(member.id),
                Payment.group_id == group.id
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
            typer.echo(f"➡️  {debtor} pays {creditor} R{amount}")


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
