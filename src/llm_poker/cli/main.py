"""CLI interface for LLM Poker Arena."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from llm_poker.config import DEFAULT_MODELS, settings
from llm_poker.tournament.heads_up import HeadsUpMatch
from llm_poker.tournament.round_robin import RoundRobinTournament
from llm_poker.tournament.full_table import FullTableTournament
from llm_poker.analytics.elo import elo_system

app = typer.Typer(
    name="llm-poker",
    help="LLM Poker Arena - Multi-agent poker evaluation framework",
    add_completion=False,
)
console = Console()


def model_callback(value: str) -> str:
    """Validate model name format."""
    if "/" not in value:
        raise typer.BadParameter(
            f"Model must be in format 'provider/model-name', got: {value}"
        )
    return value


@app.command()
def hand(
    model1: str = typer.Option(
        ...,
        "--model1", "-m1",
        help="First model (e.g., openai/gpt-4o)",
        callback=model_callback,
    ),
    model2: str = typer.Option(
        ...,
        "--model2", "-m2",
        help="Second model",
        callback=model_callback,
    ),
    stack: int = typer.Option(
        1_500_000,
        "--stack", "-s",
        help="Starting stack for each player",
    ),
    small_blind: int = typer.Option(
        5_000,
        "--sb",
        help="Small blind amount",
    ),
    big_blind: int = typer.Option(
        10_000,
        "--bb",
        help="Big blind amount",
    ),
    no_db: bool = typer.Option(
        False,
        "--no-db",
        help="Don't log to database",
    ),
):
    """Play a single hand between two models (for debugging)."""
    console.print("\n[bold]Playing single hand[/bold]")
    console.print(f"  {model1} vs {model2}")

    async def run():
        match = HeadsUpMatch(
            model1=model1,
            model2=model2,
            num_hands=1,
            starting_stack=stack,
            small_blind=small_blind,
            big_blind=big_blind,
            log_to_db=not no_db,
        )
        result = await match.run()
        match.print_result(result)

        # Print detailed decision log
        if result.hand_results:
            hand_result = result.hand_results[0]
            console.print("\n[bold]Hand Details[/bold]")
            console.print(f"  Board: {hand_result.board_cards}")
            console.print(f"  Pot: ${hand_result.pot_size:,}")
            console.print(f"  Decisions: {hand_result.decisions_count}")

    asyncio.run(run())


@app.command()
def heads_up(
    model1: str = typer.Option(
        ...,
        "--model1", "-m1",
        help="First model",
        callback=model_callback,
    ),
    model2: str = typer.Option(
        ...,
        "--model2", "-m2",
        help="Second model",
        callback=model_callback,
    ),
    hands: int = typer.Option(
        100,
        "--hands", "-n",
        help="Number of hands to play",
    ),
    stack: int = typer.Option(
        1_500_000,
        "--stack", "-s",
        help="Starting stack",
    ),
    small_blind: int = typer.Option(
        5_000,
        "--sb",
        help="Small blind",
    ),
    big_blind: int = typer.Option(
        10_000,
        "--bb",
        help="Big blind",
    ),
    escalate: bool = typer.Option(
        False,
        "--escalate",
        help="Use escalating blind structure",
    ),
    no_db: bool = typer.Option(
        False,
        "--no-db",
        help="Don't log to database",
    ),
):
    """Run a heads-up match between two models."""
    async def run():
        match = HeadsUpMatch(
            model1=model1,
            model2=model2,
            num_hands=hands,
            starting_stack=stack,
            small_blind=small_blind,
            big_blind=big_blind,
            use_blind_structure=escalate,
            log_to_db=not no_db,
        )
        result = await match.run()
        match.print_result(result)

        # Update ELO
        if result.winner:
            loser = model2 if result.winner == model1 else model1
            new_winner_elo, new_loser_elo = elo_system.update_ratings(
                result.winner, loser, draw=False
            )
            elo_system.save_to_file()  # Persist to disk
            console.print("\n[bold]ELO Updates[/bold]")
            console.print(f"  {result.winner.split('/')[-1]}: {new_winner_elo}")
            console.print(f"  {loser.split('/')[-1]}: {new_loser_elo}")

    asyncio.run(run())


@app.command()
def round_robin(
    hands_per_match: int = typer.Option(
        100,
        "--hands", "-n",
        help="Hands per match",
    ),
    stack: int = typer.Option(
        1_500_000,
        "--stack", "-s",
        help="Starting stack",
    ),
    small_blind: int = typer.Option(
        5_000,
        "--sb",
        help="Small blind",
    ),
    big_blind: int = typer.Option(
        10_000,
        "--bb",
        help="Big blind",
    ),
    models: Optional[list[str]] = typer.Option(
        None,
        "--model", "-m",
        help="Models to include (can specify multiple, defaults to all)",
    ),
    no_db: bool = typer.Option(
        False,
        "--no-db",
        help="Don't log to database",
    ),
):
    """Run a round robin tournament (all pairs play each other)."""
    model_list = list(models) if models else DEFAULT_MODELS

    console.print("\n[bold]Round Robin Tournament[/bold]")
    console.print(f"  Models: {len(model_list)}")
    console.print(f"  Matches: {len(model_list) * (len(model_list) - 1) // 2}")
    console.print(f"  Hands per match: {hands_per_match}")

    async def run():
        tournament = RoundRobinTournament(
            models=model_list,
            hands_per_match=hands_per_match,
            starting_stack=stack,
            small_blind=small_blind,
            big_blind=big_blind,
            log_to_db=not no_db,
        )
        result = await tournament.run()
        tournament.print_standings(result)

    asyncio.run(run())


@app.command()
def full_table(
    max_hands: int = typer.Option(
        1000,
        "--max-hands", "-n",
        help="Maximum hands before ending",
    ),
    stack: int = typer.Option(
        1_500_000,
        "--stack", "-s",
        help="Starting stack",
    ),
    small_blind: int = typer.Option(
        5_000,
        "--sb",
        help="Initial small blind",
    ),
    big_blind: int = typer.Option(
        10_000,
        "--bb",
        help="Initial big blind",
    ),
    hands_per_level: int = typer.Option(
        20,
        "--level-hands",
        help="Hands before blinds increase",
    ),
    models: Optional[list[str]] = typer.Option(
        None,
        "--model", "-m",
        help="Models to include (max 6, defaults to all)",
    ),
    no_db: bool = typer.Option(
        False,
        "--no-db",
        help="Don't log to database",
    ),
):
    """Run a 6-player tournament until one player wins."""
    model_list = (list(models) if models else DEFAULT_MODELS)[:6]

    if len(model_list) < 2:
        console.print("[red]Need at least 2 models for a tournament[/red]")
        raise typer.Exit(1)

    console.print("\n[bold]Full Table Tournament[/bold]")
    console.print(f"  Players: {len(model_list)}")
    console.print(f"  Starting stack: ${stack:,}")
    console.print(f"  Initial blinds: ${small_blind:,}/${big_blind:,}")

    async def run():
        tournament = FullTableTournament(
            models=model_list,
            starting_stack=stack,
            small_blind=small_blind,
            big_blind=big_blind,
            hands_per_blind_level=hands_per_level,
            max_hands=max_hands,
            log_to_db=not no_db,
        )
        result = await tournament.run()
        tournament.print_result(result)

    asyncio.run(run())


@app.command()
def leaderboard():
    """Show ELO leaderboard."""
    ratings = elo_system.get_leaderboard()

    if not ratings:
        console.print("\n[yellow]No ELO data yet. Run some matches first![/yellow]")
        return

    table = Table(title="ELO Leaderboard")
    table.add_column("Rank", justify="center")
    table.add_column("Model", style="cyan")
    table.add_column("ELO", justify="right")
    table.add_column("W-L-D", justify="center")
    table.add_column("Games", justify="right")

    for i, rating in enumerate(ratings, 1):
        model_short = rating.model.split("/")[-1]
        wld = f"{rating.wins}-{rating.losses}-{rating.draws}"

        table.add_row(
            str(i),
            model_short,
            str(rating.rating),
            wld,
            str(rating.games_played),
        )

    console.print(table)


@app.command()
def models():
    """List available default models."""
    console.print("\n[bold]Default Models[/bold]")

    table = Table()
    table.add_column("Model", style="cyan")
    table.add_column("Provider")

    for model in DEFAULT_MODELS:
        provider, name = model.split("/", 1)
        table.add_row(model, provider)

    console.print(table)

    console.print("\n[dim]You can use any model supported by LiteLLM.[/dim]")
    console.print("[dim]Format: provider/model-name (e.g., openai/gpt-4o)[/dim]")


@app.command()
def serve(
    host: str = typer.Option(
        "0.0.0.0",
        "--host", "-h",
        help="Host to bind to",
    ),
    port: int = typer.Option(
        8000,
        "--port", "-p",
        help="Port to bind to",
    ),
    reload: bool = typer.Option(
        False,
        "--reload", "-r",
        help="Enable auto-reload for development",
    ),
):
    """Start the FastAPI REST API server."""
    import uvicorn

    console.print("\n[bold]Starting LLM Poker Arena API[/bold]")
    console.print(f"  Host: {host}")
    console.print(f"  Port: {port}")
    console.print(f"  Docs: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/docs")
    console.print()

    uvicorn.run(
        "llm_poker.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def config():
    """Show current configuration."""
    console.print("\n[bold]Current Configuration[/bold]")

    table = Table()
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Default Starting Stack", f"${settings.default_starting_stack:,}")
    table.add_row("Default Small Blind", f"${settings.default_small_blind:,}")
    table.add_row("Default Big Blind", f"${settings.default_big_blind:,}")
    table.add_row("LLM Temperature", str(settings.llm_temperature))
    table.add_row("LLM Timeout", f"{settings.llm_timeout}s")
    table.add_row("LLM Retries", str(settings.llm_retries))
    table.add_row("Equity Sample Count", str(settings.equity_sample_count))

    # Check API keys
    api_keys = [
        ("OpenAI", bool(settings.openai_api_key)),
        ("Anthropic", bool(settings.anthropic_api_key)),
        ("Google", bool(settings.google_api_key)),
        ("Groq", bool(settings.groq_api_key)),
        ("Mistral", bool(settings.mistral_api_key)),
        ("DeepSeek", bool(settings.deepseek_api_key)),
    ]

    console.print(table)

    console.print("\n[bold]API Keys[/bold]")
    for name, configured in api_keys:
        status = "[green]Configured[/green]" if configured else "[red]Not Set[/red]"
        console.print(f"  {name}: {status}")

    # Supabase
    supabase_configured = bool(settings.supabase_url and settings.supabase_key)
    status = "[green]Configured[/green]" if supabase_configured else "[yellow]Not Set (DB logging disabled)[/yellow]"
    console.print(f"\n  Supabase: {status}")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
