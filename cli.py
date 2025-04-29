import typer
from typing_extensions import Annotated
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Member, Group

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




if __name__ == "__main__":
    app()
