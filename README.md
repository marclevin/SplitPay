# Introduction
EcoCLI is a Python-based command-line interface (CLI) application built using Typer for managing groups and members in a structured, database-backed system. It uses PostgreSQL as the primary database, with SQLAlchemy ORM for database interaction and Alembic for schema migrations.

The application provides commands for creating, listing, selecting, and modifying groups and members, along with utilities for managing session state (such as the currently active group). Most operations are context-aware, meaning they operate on whichever group is currently selected by the user.
