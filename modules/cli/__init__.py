"""
CLI Client Module.

Interactive command-line client built with Typer for communicating
with the backend API.

Architecture:
- CLI is a thin presentation layer
- All business logic lives in the backend
- CLI calls backend via HTTP (httpx)
- Sends X-Frontend-ID: cli header for log routing

Usage:
    python cli_typer.py --help
    python cli_typer.py status
    python cli_typer.py health
    python cli_typer.py shell  # Interactive mode
"""
