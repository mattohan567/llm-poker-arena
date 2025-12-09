"""Round robin tournament runner."""

import asyncio
import itertools
from dataclasses import dataclass, field
from typing import Callable
from uuid import UUID

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from llm_poker.tournament.heads_up import HeadsUpMatch, MatchResult
from llm_poker.config import DEFAULT_MODELS


@dataclass
class RoundRobinResult:
    """Result of a round robin tournament."""
    models: list[str]
    matches: list[MatchResult]
    standings: list[dict]  # [{model, wins, losses, profit, elo}] sorted by profit
    total_hands: int
    total_tokens: int
    total_cost: float


class RoundRobinTournament:
    """Runs heads-up matches between all pairs of models."""

    def __init__(
        self,
        models: list[str] | None = None,
        hands_per_match: int = 100,
        starting_stack: int = 1_500_000,
        small_blind: int = 5_000,
        big_blind: int = 10_000,
        log_to_db: bool = True,
        on_match_complete: Callable[[int, int, MatchResult], None] | None = None,
    ):
        """
        Initialize round robin tournament.

        Args:
            models: List of model names (defaults to DEFAULT_MODELS)
            hands_per_match: Number of hands per heads-up match
            starting_stack: Starting stack for each player
            small_blind: Small blind amount
            big_blind: Big blind amount
            log_to_db: Whether to log to database
            on_match_complete: Callback(match_num, total_matches, result)
        """
        self.models = models or DEFAULT_MODELS
        self.hands_per_match = hands_per_match
        self.starting_stack = starting_stack
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.log_to_db = log_to_db
        self.on_match_complete = on_match_complete

        # Generate all matchups
        self.matchups = list(itertools.combinations(self.models, 2))

        # Results tracking
        self.match_results: list[MatchResult] = []

        # Per-model statistics
        self.model_stats: dict[str, dict] = {
            model: {
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "profit": 0,
                "hands_played": 0,
                "tokens": 0,
                "cost": 0.0,
            }
            for model in self.models
        }

        self.console = Console()

    async def run(self) -> RoundRobinResult:
        """
        Run the complete round robin tournament.

        Returns:
            RoundRobinResult with tournament statistics
        """
        total_matches = len(self.matchups)

        self.console.print("\n[bold]Starting Round Robin Tournament[/bold]")
        self.console.print(f"  {len(self.models)} models, {total_matches} matches")
        self.console.print(f"  {self.hands_per_match} hands per match")
        self.console.print()

        # Run each matchup
        for i, (model1, model2) in enumerate(self.matchups, 1):
            self.console.print(f"\n[bold]Match {i}/{total_matches}[/bold]")
            self.console.print(f"  {model1.split('/')[-1]} vs {model2.split('/')[-1]}")

            # Run heads-up match
            match = HeadsUpMatch(
                model1=model1,
                model2=model2,
                num_hands=self.hands_per_match,
                starting_stack=self.starting_stack,
                small_blind=self.small_blind,
                big_blind=self.big_blind,
                log_to_db=self.log_to_db,
            )

            result = await match.run()
            self.match_results.append(result)

            # Update statistics
            self._update_stats(result)

            # Print match result
            match.print_result(result)

            # Callback
            if self.on_match_complete:
                self.on_match_complete(i, total_matches, result)

        # Build final result
        return self._build_result()

    def _update_stats(self, result: MatchResult):
        """Update model statistics from match result."""
        model1, model2 = result.model1, result.model2

        # Update wins/losses
        if result.winner == model1:
            self.model_stats[model1]["wins"] += 1
            self.model_stats[model2]["losses"] += 1
        elif result.winner == model2:
            self.model_stats[model2]["wins"] += 1
            self.model_stats[model1]["losses"] += 1
        else:
            self.model_stats[model1]["ties"] += 1
            self.model_stats[model2]["ties"] += 1

        # Update profit
        self.model_stats[model1]["profit"] += result.model1_profit
        self.model_stats[model2]["profit"] += result.model2_profit

        # Update other stats
        self.model_stats[model1]["hands_played"] += result.hands_played
        self.model_stats[model2]["hands_played"] += result.hands_played
        self.model_stats[model1]["tokens"] += result.total_tokens // 2
        self.model_stats[model2]["tokens"] += result.total_tokens // 2
        self.model_stats[model1]["cost"] += result.total_cost / 2
        self.model_stats[model2]["cost"] += result.total_cost / 2

    def _build_result(self) -> RoundRobinResult:
        """Build final tournament result."""
        # Build standings sorted by profit
        standings = []
        for model, stats in self.model_stats.items():
            standings.append({
                "model": model,
                "wins": stats["wins"],
                "losses": stats["losses"],
                "ties": stats["ties"],
                "profit": stats["profit"],
                "hands_played": stats["hands_played"],
                "tokens": stats["tokens"],
                "cost": stats["cost"],
            })

        standings.sort(key=lambda x: x["profit"], reverse=True)

        total_hands = sum(r.hands_played for r in self.match_results)
        total_tokens = sum(r.total_tokens for r in self.match_results)
        total_cost = sum(r.total_cost for r in self.match_results)

        return RoundRobinResult(
            models=self.models,
            matches=self.match_results,
            standings=standings,
            total_hands=total_hands,
            total_tokens=total_tokens,
            total_cost=total_cost,
        )

    def print_standings(self, result: RoundRobinResult):
        """Print tournament standings."""
        self.console.print("\n[bold]Tournament Standings[/bold]")

        table = Table()
        table.add_column("Rank", justify="center")
        table.add_column("Model", style="cyan")
        table.add_column("W-L-T", justify="center")
        table.add_column("Profit", justify="right")
        table.add_column("Hands", justify="right")
        table.add_column("Cost", justify="right")

        for i, standing in enumerate(result.standings, 1):
            model_short = standing["model"].split("/")[-1]
            wlt = f"{standing['wins']}-{standing['losses']}-{standing['ties']}"
            profit = standing["profit"]
            profit_color = "green" if profit >= 0 else "red"

            table.add_row(
                str(i),
                model_short,
                wlt,
                f"[{profit_color}]${profit:+,}[/{profit_color}]",
                f"{standing['hands_played']:,}",
                f"${standing['cost']:.2f}",
            )

        self.console.print(table)

        self.console.print(f"\nTotal hands: {result.total_hands:,}")
        self.console.print(f"Total tokens: {result.total_tokens:,}")
        self.console.print(f"Total cost: ${result.total_cost:.2f}")
