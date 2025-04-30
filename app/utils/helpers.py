import os
from contextlib import contextmanager

import typer
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Group

SESSION_FILE = ".eco_session"


def set_active_group_id(group_id: int):
    with open(SESSION_FILE, "w") as f:
        f.write(str(group_id))


def get_active_group_id() -> int | None:
    if not os.path.exists(SESSION_FILE):
        return None
    with open(SESSION_FILE, "r") as f:
        return int(f.read().strip())


def clear_active_group():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)


@contextmanager
def get_db_and_group() -> tuple[Session, Group] | None:
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
def get_db() -> Session:
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
            return selected.id
    except ValueError:
        pass

    typer.echo("❌ Invalid selection.")
    raise typer.Exit()
