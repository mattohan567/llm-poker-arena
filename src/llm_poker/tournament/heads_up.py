"""Heads-up match runner for two players."""

from dataclasses import dataclass, field
from typing import Callable
from uuid import UUID

from rich.console import Console
from rich.table import Table

from llm_poker.agents.poker_agent import PokerAgent
from llm_poker.engine.hand_manager import HandManager, HandResult
from llm_poker.tournament.blind_structure import BlindStructure
from llm_poker.storage.models import TournamentCreate, ParticipantCreate
from llm_poker.storage.repositories import (
    TournamentRepository, ParticipantRepository,
)


@dataclass
class MatchResult:
    """Result of a heads-up match."""
    model1: str
    model2: str
    hands_played: int
    model1_profit: int
    model2_profit: int
    model1_final_stack: int
    model2_final_stack: int
    winner: str | None  # None if tied
    hand_results: list[HandResult] = field(default_factory=list)
    total_tokens: int = 0
    total_cost: float = 0.0


class HeadsUpMatch:
    """Runs a heads-up match between two LLM agents."""

    def __init__(
        self,
        model1: str,
        model2: str,
        num_hands: int = 100,
        starting_stack: int = 1_500_000,
        small_blind: int = 5_000,
        big_blind: int = 10_000,
        use_blind_structure: bool = False,
        log_to_db: bool = True,
        on_hand_complete: Callable[[int, HandResult], None] | None = None,
    ):
        """
        Initialize heads-up match.

        Args:
            model1: First model name (e.g., "openai/gpt-4o")
            model2: Second model name
            num_hands: Number of hands to play
            starting_stack: Starting stack for each player
            small_blind: Small blind amount
            big_blind: Big blind amount
            use_blind_structure: Whether to use escalating blinds
            log_to_db: Whether to log to database
            on_hand_complete: Callback after each hand
        """
        self.model1 = model1
        self.model2 = model2
        self.num_hands = num_hands
        self.starting_stack = starting_stack
        self.initial_small_blind = small_blind
        self.initial_big_blind = big_blind
        self.use_blind_structure = use_blind_structure
        self.log_to_db = log_to_db
        self.on_hand_complete = on_hand_complete

        # Initialize agents
        self.agent1 = PokerAgent(model=model1, player_name=model1.split("/")[-1])
        self.agent2 = PokerAgent(model=model2, player_name=model2.split("/")[-1])

        # Current stacks
        self.stacks = [starting_stack, starting_stack]

        # Blind structure
        self.blind_structure = None
        if use_blind_structure:
            self.blind_structure = BlindStructure(
                initial_small_blind=small_blind,
                initial_big_blind=big_blind,
            )

        # Database IDs
        self.tournament_id: UUID | None = None
        self.participant_ids: list[UUID] = []

        # Results tracking
        self.hand_results: list[HandResult] = []
        self.button_position = 0  # 0 = model1 has button

        # Console for output
        self.console = Console()

    async def run(self) -> MatchResult:
        """
        Run the complete heads-up match.

        Returns:
            MatchResult with match statistics
        """
        # Initialize tournament in database
        if self.log_to_db:
            await self._init_tournament()

        self.console.print("\n[bold]Starting Heads-Up Match[/bold]")
        self.console.print(f"  {self.model1} vs {self.model2}")
        self.console.print(f"  {self.num_hands} hands, ${self.starting_stack:,} starting stack")
        self.console.print()

        # Play hands
        for hand_num in range(1, self.num_hands + 1):
            # Check if either player is eliminated
            if min(self.stacks) <= 0:
                self.console.print(f"\n[bold red]Player eliminated after {hand_num - 1} hands![/bold red]")
                break

            # Get current blinds
            if self.blind_structure:
                sb, bb = self.blind_structure.get_blinds()
            else:
                sb, bb = self.initial_small_blind, self.initial_big_blind

            # Determine seat order (button/SB first, then BB)
            if self.button_position == 0:
                agents = [self.agent1, self.agent2]
                stacks = self.stacks.copy()
            else:
                agents = [self.agent2, self.agent1]
                stacks = [self.stacks[1], self.stacks[0]]

            # Create and run hand
            hand_manager = HandManager(
                agents=agents,
                starting_stacks=stacks,
                small_blind=sb,
                big_blind=bb,
                hand_number=hand_num,
                tournament_id=self.tournament_id,
                participant_ids=self._get_ordered_participant_ids(),
                log_to_db=self.log_to_db,
            )

            result = await hand_manager.play_hand()
            self.hand_results.append(result)

            # Update stacks
            for player_result in result.player_results:
                original_idx = self._get_original_index(player_result["player_index"])
                self.stacks[original_idx] = player_result["ending_stack"]

            # Update blind structure
            if self.blind_structure:
                self.blind_structure.hand_completed()

            # Rotate button
            self.button_position = 1 - self.button_position

            # Callback
            if self.on_hand_complete:
                self.on_hand_complete(hand_num, result)

            # Progress output every 10 hands
            if hand_num % 10 == 0:
                self._print_progress(hand_num)

        # Finalize tournament
        if self.log_to_db:
            await self._finalize_tournament()

        # Build result
        return self._build_result()

    async def _init_tournament(self):
        """Initialize tournament in database."""
        repo = TournamentRepository()
        participant_repo = ParticipantRepository()

        tournament = repo.create(TournamentCreate(
            tournament_type="heads_up",
            config={
                "model1": self.model1,
                "model2": self.model2,
                "num_hands": self.num_hands,
                "starting_stack": self.starting_stack,
                "small_blind": self.initial_small_blind,
                "big_blind": self.initial_big_blind,
                "use_blind_structure": self.use_blind_structure,
            },
        ))
        self.tournament_id = tournament.id

        # Create participants
        participants = participant_repo.create_many([
            ParticipantCreate(
                tournament_id=tournament.id,
                model_name=self.model1,
                seat_position=0,
                starting_stack=self.starting_stack,
            ),
            ParticipantCreate(
                tournament_id=tournament.id,
                model_name=self.model2,
                seat_position=1,
                starting_stack=self.starting_stack,
            ),
        ])
        self.participant_ids = [p.id for p in participants]

        # Update status to running
        repo.update_status(tournament.id, "running")

    async def _finalize_tournament(self):
        """Finalize tournament in database."""
        repo = TournamentRepository()
        participant_repo = ParticipantRepository()

        # Update participant final results
        for i, participant_id in enumerate(self.participant_ids):
            participant_repo.update_final_results(
                participant_id=participant_id,
                final_stack=self.stacks[i],
                final_position=1 if self.stacks[i] > self.stacks[1 - i] else 2,
                total_hands=len(self.hand_results),
            )

        # Update tournament status
        repo.update_status(self.tournament_id, "completed")

    def _get_ordered_participant_ids(self) -> list[UUID]:
        """Get participant IDs in current seating order."""
        if not self.participant_ids:
            return []

        if self.button_position == 0:
            return self.participant_ids
        else:
            return [self.participant_ids[1], self.participant_ids[0]]

    def _get_original_index(self, hand_index: int) -> int:
        """Convert hand index back to original player index."""
        if self.button_position == 0:
            return hand_index
        else:
            return 1 - hand_index

    def _print_progress(self, hand_num: int):
        """Print progress update."""
        self.console.print(
            f"  Hand {hand_num}/{self.num_hands}: "
            f"{self.model1.split('/')[-1]}: ${self.stacks[0]:,} | "
            f"{self.model2.split('/')[-1]}: ${self.stacks[1]:,}"
        )

    def _build_result(self) -> MatchResult:
        """Build final match result."""
        model1_profit = self.stacks[0] - self.starting_stack
        model2_profit = self.stacks[1] - self.starting_stack

        winner = None
        if model1_profit > model2_profit:
            winner = self.model1
        elif model2_profit > model1_profit:
            winner = self.model2

        total_tokens = sum(r.total_tokens for r in self.hand_results)
        total_cost = sum(r.total_cost for r in self.hand_results)

        return MatchResult(
            model1=self.model1,
            model2=self.model2,
            hands_played=len(self.hand_results),
            model1_profit=model1_profit,
            model2_profit=model2_profit,
            model1_final_stack=self.stacks[0],
            model2_final_stack=self.stacks[1],
            winner=winner,
            hand_results=self.hand_results,
            total_tokens=total_tokens,
            total_cost=total_cost,
        )

    def print_result(self, result: MatchResult):
        """Print match result summary."""
        self.console.print("\n[bold]Match Complete![/bold]")

        table = Table(title="Final Results")
        table.add_column("Model", style="cyan")
        table.add_column("Final Stack", justify="right")
        table.add_column("Profit/Loss", justify="right")
        table.add_column("Result", style="bold")

        m1_result = "[green]WIN[/green]" if result.winner == self.model1 else (
            "[red]LOSS[/red]" if result.winner else "[yellow]TIE[/yellow]"
        )
        m2_result = "[green]WIN[/green]" if result.winner == self.model2 else (
            "[red]LOSS[/red]" if result.winner else "[yellow]TIE[/yellow]"
        )

        profit1_color = "green" if result.model1_profit >= 0 else "red"
        profit2_color = "green" if result.model2_profit >= 0 else "red"

        table.add_row(
            result.model1.split("/")[-1],
            f"${result.model1_final_stack:,}",
            f"[{profit1_color}]${result.model1_profit:+,}[/{profit1_color}]",
            m1_result,
        )
        table.add_row(
            result.model2.split("/")[-1],
            f"${result.model2_final_stack:,}",
            f"[{profit2_color}]${result.model2_profit:+,}[/{profit2_color}]",
            m2_result,
        )

        self.console.print(table)

        self.console.print(f"\nHands played: {result.hands_played}")
        self.console.print(f"Total tokens: {result.total_tokens:,}")
        self.console.print(f"Total cost: ${result.total_cost:.4f}")
