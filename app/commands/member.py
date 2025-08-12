import random

import typer
from typing_extensions import Annotated
from app.utils.helpers import get_db_and_group, MEMBER_COLORS
from app.models import Member, Group

member_app = typer.Typer(no_args_is_help=True)


@member_app.command()
def add(name: Annotated[str, typer.Argument(help="Name of the new member.")]):
    """
    Add a new member to a group.
    """
    with get_db_and_group() as (db, group):
        # Check for existing member with the same name in the same group
        existing_member = db.query(Member).filter_by(name=name, group_id=group.id).first()
        if existing_member:
            # If a member with the same name already exists, do not add
            typer.echo(f"❌ Member '{name}' already exists in group '{group.name}'.")
            raise typer.Exit()

        new_member = Member(name=name, group_id=group.id, color=random.choice(MEMBER_COLORS))
        db.add(new_member)
        typer.echo(f"✅ Added member '{name}' to group '{group.name}'.")


@member_app.command()
def show(group_name: Annotated[str, typer.Option(help="Name of the group to list members from.")] = None):
    """
    List all members in a group.
    """
    with get_db_and_group() as (db, group):
        if group_name:
            group = db.query(Group).filter_by(name=group_name).first()
            if not group:
                typer.echo(f"❌ Group '{group_name}' not found.")
                raise typer.Exit()
        else:
            group_name = group.name

        members = db.query(Member).filter_by(group_id=group.id).all()
        if not members:
            typer.echo("No members found in this group.")
            return

        typer.echo(f"👥 Members in '{group_name}':")
        for m in members:
            typer.echo(f"• {m.name} (ID: {m.id})")


@member_app.command()
def delete(name: Annotated[str, typer.Argument(help="Name of the member to delete.")]):
    """
    Delete a member from a group.
    """
    with get_db_and_group() as (db, group):
        member = db.query(Member).filter_by(name=name, group_id=group.id).first()
        if not member:
            typer.echo(f"❌ Member '{name}' not found in group '{group.name}'.")
            raise typer.Exit()

        db.delete(member)
        typer.echo(f"✅ Deleted member '{name}' from group '{group.name}'.")
