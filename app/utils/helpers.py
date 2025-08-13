import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator

import typer
from rich.console import Console
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Group

SESSION_FILE = ".eco_session"

MEMBER_COLORS = [
    "bright_blue",
    "bright_magenta",
    "bright_yellow",
    "bright_cyan",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "bright_white",
]
console = Console()


def money(x: float) -> str:
    color = "green" if x >= 0 else "red"
    neg = "-" if x < 0 else ""
    x = abs(x)
    return f"[{color}]{neg}R{round(x + 1e-9, 2):,.2f}[/{color}]"


def set_active_group_id(group_id: int):
    with open(SESSION_FILE, "w") as f:
        f.write(str(group_id))
        f.close()


def date_str(d) -> str:
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d")
    try:
        # handle date, datetime.date, or string-ish
        return d.strftime("%Y-%m-%d")
    except AttributeError:
        return str(d)


def get_active_group_id() -> int | None:
    if not os.path.exists(SESSION_FILE):
        return None
    with open(SESSION_FILE, "r") as f:
        return int(f.read().strip())


def clear_active_group():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)


@contextmanager
def get_db_and_group() -> Generator[tuple[Any, Any], Any, None]:
    db = SessionLocal()
    try:
        group_id = resolve_or_prompt_group(db)
        group = db.query(Group).filter_by(id=group_id).first()
        if not group:
            typer.echo("⚠️ Selected group no longer exists.")
            clear_active_group()
            raise typer.Exit()
        yield db, group
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


@contextmanager
def get_db() -> Generator[Any, Any, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def resolve_or_prompt_group(db: Session) -> int:
    group_id = get_active_group_id()
    if group_id:
        return group_id

    groups = db.query(Group).all()
    if not groups:
        typer.echo("❌ No groups found. Please create one first.")
        raise typer.Exit()

    if len(groups) == 1:
        selected = groups[0]
        typer.echo(f"✅ Automatically selected group '{selected.name}' (id: {selected.id}) as active.")
        set_active_group_id(selected.id)
        return selected.id

    typer.echo("📂 Select a group:")
    for i, group in enumerate(groups, 1):
        typer.echo(f"{i}. {group.name}")

    choice = typer.prompt("Enter the number of the group")
    try:
        index = int(choice) - 1
        if 0 <= index < len(groups):
            selected = groups[index]
            set_active_group_id(selected.id)
            typer.echo(f"✅ Selected group '{selected.name}' (id: {selected.id}) as active.")
            return selected.id
    except ValueError:
        pass

    typer.echo("❌ Invalid selection.")
    raise typer.Exit()


def min_cash_flow_settlements(balances: dict[str, float]) -> list[tuple[str, str, float]]:
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
