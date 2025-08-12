import typer

from app.models import Group
from app.utils.helpers import get_db, set_active_group_id, clear_active_group, get_db_and_group, get_active_group_id

group_app = typer.Typer(no_args_is_help=True,short_help="Group management commands.")


# Group Management Commands
@group_app.command()
def select():
    """
    Select an active group session.
    """
    with get_db() as db:
        groups = db.query(Group).all()
        if not groups:
            typer.echo("❌ No groups found. Please create one first.")
            raise typer.Exit()
        typer.echo("📂 Available Groups:")
        for i, group in enumerate(groups, 1):
            typer.echo(f"{i}. {group.name}")

        choice = typer.prompt("Enter the number of the group")
        try:
            index = int(choice) - 1
            if 0 <= index < len(groups):
                selected = groups[index]
                set_active_group_id(selected.id)
                typer.echo(f"✅ Selected group '{selected.name}' (id: {selected.id}) as active.")
                return
        except ValueError:
            pass
    typer.echo("❌ Invalid selection.")
    raise typer.Exit()


@group_app.command()
def create(name: str):
    """
    Create a new group.
    """
    with get_db() as db:
        existing_group = db.query(Group).filter_by(name=name).first()
        if existing_group:
            typer.echo(f"❌ Group '{name}' already exists.")
            raise typer.Exit()

        new_group = Group(name=name)
        db.add(new_group)
        db.commit()
        set_active_group_id(new_group.id)
        typer.echo(f"✅ Created group '{name}' (id: {new_group.id}) and set it as active.")


@group_app.command()
def clear_session():
    """
    Clear the current group session.
    """
    clear_active_group()
    typer.echo("🧹 Session cleared.")


@group_app.command()
def current():
    """
    Show the currently selected group.
    """
    with get_db_and_group() as (db, group):
        typer.echo(f"📁 Current group: '{group.name}' (ID: {group.id})")


@group_app.command()
def show():
    """
    List all groups.
    """
    with get_db() as db:
        groups = db.query(Group).all()
        if not groups:
            typer.echo("❌ No groups found, please create one first.")
            raise typer.Exit()
        typer.echo("📂 Groups:")
        for group in groups:
            typer.echo(f"• {group.name} (ID: {group.id})")


@group_app.command()
def delete(name: str):
    """
    Delete a group by name.
    WARNING: This deletes all associated members, expenses, and payments.
    """
    with get_db() as db:
        group = db.query(Group).filter_by(name=name).first()
        if not group:
            typer.echo(f"❌ Group '{name}' not found.")
            raise typer.Exit()

        # Check if the group is currently selected
        if group.id == get_active_group_id():
            clear_active_group()

        db.delete(group)
        db.commit()
        typer.echo(f"✅ Deleted group '{name}'.")
