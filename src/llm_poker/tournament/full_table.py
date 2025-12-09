"""Full table (6-player) tournament runner."""

import asyncio
from dataclasses import dataclass, field
from typing import Callable
from uuid import UUID

from rich.console import Console
from rich.table import Table

from llm_poker.agents.poker_agent import PokerAgent
from llm_poker.engine.hand_manager import HandManager, HandResult
from llm_poker.tournament.blind_structure import BlindStructure
from llm_poker.storage.models import TournamentCreate, ParticipantCreate
from llm_poker.storage.repositories import TournamentRepository, ParticipantRepository
from llm_poker.config import DEFAULT_MODELS


@dataclass
class FullTableResult:
    """Result of a full table tournament."""
    models: list[str]
    final_standings: list[dict]  # [{model, final_stack, position, hands_played, eliminated_at}]
    hands_played: int
    total_tokens: int
    total_cost: float
    hand_results: list[HandResult] = field(default_factory=list)


class FullTableTournament:
    """Runs a 6-player tournament until one player has all chips."""

    def __init__(
        self,
        models: list[str] | None = None,
        starting_stack: int = 1_500_000,
        small_blind: int = 5_000,
        big_blind: int = 10_000,
        hands_per_blind_level: int = 20,
        blind_multiplier: float = 1.5,
        max_hands: int = 1000,
        log_to_db: bool = True,
        on_hand_complete: Callable[[int, HandResult], None] | None = None,
        on_elimination: Callable[[str, int], None] | None = None,
    ):
        """
        Initialize full table tournament.

        Args:
            models: List of 6 model names (defaults to DEFAULT_MODELS)
            starting_stack: Starting stack for each player
            small_blind: Initial small blind
            big_blind: Initial big blind
            hands_per_blind_level: Hands before blinds increase
            blind_multiplier: Blind increase multiplier
            max_hands: Maximum hands before ending (winner by chip count)
            log_to_db: Whether to log to database
            on_hand_complete: Callback after each hand
            on_elimination: Callback when player eliminated (model, position)
        """
        self.models = (models or DEFAULT_MODELS)[:6]  # Limit to 6 players
        if len(self.models) < 2:
            raise ValueError("Need at least 2 models for a tournament")

        self.starting_stack = starting_stack
        self.max_hands = max_hands
        self.log_to_db = log_to_db
        self.on_hand_complete = on_hand_complete
        self.on_elimination = on_elimination

        # Initialize agents
        self.agents = [
            PokerAgent(model=model, player_name=model.split("/")[-1])
            for model in self.models
        ]

        # Stacks for all players
        self.stacks = [starting_stack] * len(self.models)

        # Active players (not eliminated)
        self.active_players = list(range(len(self.models)))

        # Blind structure
        self.blind_structure = BlindStructure(
            initial_small_blind=small_blind,
            initial_big_blind=big_blind,
            hands_per_level=hands_per_blind_level,
            multiplier=blind_multiplier,
        )

        # Button position
        self.button_position = 0

        # Tournament tracking
        self.tournament_id: UUID | None = None
        self.participant_ids: list[UUID] = []
        self.hand_results: list[HandResult] = []
        self.eliminations: list[dict] = []

        self.console = Console()

    async def run(self) -> FullTableResult:
        """
        Run the full table tournament.

        Returns:
            FullTableResult with tournament statistics
        """
        # Initialize tournament in database
        if self.log_to_db:
            await self._init_tournament()

        self.console.print("\n[bold]Starting Full Table Tournament[/bold]")
        self.console.print(f"  {len(self.models)} players")
        self.console.print(f"  ${self.starting_stack:,} starting stack")
        self.console.print(f"  Blinds: ${self.blind_structure.get_blinds()[0]:,}/${self.blind_structure.get_blinds()[1]:,}")
        self.console.print()

        hand_num = 0

        while len(self.active_players) > 1 and hand_num < self.max_hands:
            hand_num += 1

            # Get current blinds
            sb, bb = self.blind_structure.get_blinds()

            # Get active agents and stacks in seat order starting from button
            active_agents = []
            active_stacks = []
            active_indices = []

            for i in self._get_seat_order():
                if i in self.active_players and self.stacks[i] > 0:
                    active_agents.append(self.agents[i])
                    active_stacks.append(self.stacks[i])
                    active_indices.append(i)

            if len(active_agents) < 2:
                break

            # Get ordered participant IDs
            ordered_participant_ids = [
                self.participant_ids[i] for i in active_indices
            ] if self.participant_ids else []

            # Create and run hand
            hand_manager = HandManager(
                agents=active_agents,
                starting_stacks=active_stacks,
                small_blind=sb,
                big_blind=bb,
                hand_number=hand_num,
                tournament_id=self.tournament_id,
                participant_ids=ordered_participant_ids,
                log_to_db=self.log_to_db,
            )

            result = await hand_manager.play_hand()
            self.hand_results.append(result)

            # Update stacks
            for j, player_result in enumerate(result.player_results):
                original_idx = active_indices[j]
                self.stacks[original_idx] = player_result["ending_stack"]

            # Check for eliminations
            await self._check_eliminations(hand_num)

            # Update blind structure
            blinds_increased = self.blind_structure.hand_completed()

            # Rotate button
            self._rotate_button()

            # Callback
            if self.on_hand_complete:
                self.on_hand_complete(hand_num, result)

            # Progress output every 10 hands
            if hand_num % 10 == 0:
                self._print_progress(hand_num)

            # Print if blinds increased
            if blinds_increased:
                new_sb, new_bb = self.blind_structure.get_blinds()
                self.console.print(f"\n[yellow]Blinds increased to ${new_sb:,}/${new_bb:,}[/yellow]")

        # Finalize tournament
        if self.log_to_db:
            await self._finalize_tournament()

        # Build result
        return self._build_result(hand_num)

    async def _init_tournament(self):
        """Initialize tournament in database."""
        repo = TournamentRepository()
        participant_repo = ParticipantRepository()

        tournament = repo.create(TournamentCreate(
            tournament_type="full_table",
            config={
                "models": self.models,
                "starting_stack": self.starting_stack,
                "initial_small_blind": self.blind_structure.initial_small_blind,
                "initial_big_blind": self.blind_structure.initial_big_blind,
                "hands_per_blind_level": self.blind_structure.hands_per_level,
                "blind_multiplier": self.blind_structure.multiplier,
                "max_hands": self.max_hands,
            },
        ))
        self.tournament_id = tournament.id

        # Create participants
        participants = participant_repo.create_many([
            ParticipantCreate(
                tournament_id=tournament.id,
                model_name=model,
                seat_position=i,
                starting_stack=self.starting_stack,
            )
            for i, model in enumerate(self.models)
        ])
        self.participant_ids = [p.id for p in participants]

        # Update status to running
        repo.update_status(tournament.id, "running")

    async def _finalize_tournament(self):
        """Finalize tournament in database."""
        repo = TournamentRepository()
        participant_repo = ParticipantRepository()

        # Calculate final positions
        remaining = [(i, self.stacks[i]) for i in self.active_players]
        remaining.sort(key=lambda x: x[1], reverse=True)

        # Update remaining players
        for position, (player_idx, stack) in enumerate(remaining, 1):
            if player_idx < len(self.participant_ids):
                participant_repo.update_final_results(
                    participant_id=self.participant_ids[player_idx],
                    final_stack=stack,
                    final_position=position,
                    total_hands=len(self.hand_results),
                )

        repo.update_status(self.tournament_id, "completed")

    async def _check_eliminations(self, hand_num: int):
        """Check for eliminated players."""
        newly_eliminated = []

        for i in self.active_players.copy():
            if self.stacks[i] <= 0:
                self.active_players.remove(i)
                position = len(self.models) - len(self.eliminations)
                newly_eliminated.append({
                    "model": self.models[i],
                    "player_index": i,
                    "position": position,
                    "eliminated_at_hand": hand_num,
                })
                self.eliminations.append(newly_eliminated[-1])

                self.console.print(
                    f"\n[red bold]{self.models[i].split('/')[-1]} eliminated "
                    f"(Position: {position})[/red bold]"
                )

                if self.on_elimination:
                    self.on_elimination(self.models[i], position)

                # Update in database
                if self.log_to_db and i < len(self.participant_ids):
                    participant_repo = ParticipantRepository()
                    participant_repo.update_final_results(
                        participant_id=self.participant_ids[i],
                        final_stack=0,
                        final_position=position,
                        total_hands=hand_num,
                    )

    def _get_seat_order(self) -> list[int]:
        """Get seat order starting from button position."""
        n = len(self.models)
        return [(self.button_position + i) % n for i in range(n)]

    def _rotate_button(self):
        """Rotate button to next active player."""
        n = len(self.models)
        for i in range(1, n + 1):
            next_pos = (self.button_position + i) % n
            if next_pos in self.active_players:
                self.button_position = next_pos
                break

    def _print_progress(self, hand_num: int):
        """Print progress update."""
        level_info = self.blind_structure.get_level_info()

        self.console.print(f"\n  Hand {hand_num} | Level {level_info['level']} "
                          f"(${level_info['small_blind']:,}/${level_info['big_blind']:,})")

        for i in self.active_players:
            model_short = self.models[i].split("/")[-1][:12]
            self.console.print(f"    {model_short}: ${self.stacks[i]:,}")

    def _build_result(self, total_hands: int) -> FullTableResult:
        """Build final tournament result."""
        # Build standings
        final_standings = []

        # Add eliminated players in order
        for elim in reversed(self.eliminations):
            final_standings.append({
                "model": elim["model"],
                "final_stack": 0,
                "position": elim["position"],
                "hands_played": elim["eliminated_at_hand"],
                "eliminated_at": elim["eliminated_at_hand"],
            })

        # Add remaining players
        remaining = [(i, self.stacks[i]) for i in self.active_players]
        remaining.sort(key=lambda x: x[1], reverse=True)

        for position, (player_idx, stack) in enumerate(remaining, 1):
            final_standings.insert(position - 1, {
                "model": self.models[player_idx],
                "final_stack": stack,
                "position": position,
                "hands_played": total_hands,
                "eliminated_at": None,
            })

        # Sort by position
        final_standings.sort(key=lambda x: x["position"])

        total_tokens = sum(r.total_tokens for r in self.hand_results)
        total_cost = sum(r.total_cost for r in self.hand_results)

        return FullTableResult(
            models=self.models,
            final_standings=final_standings,
            hands_played=total_hands,
            total_tokens=total_tokens,
            total_cost=total_cost,
            hand_results=self.hand_results,
        )

    def print_result(self, result: FullTableResult):
        """Print tournament result."""
        self.console.print("\n[bold]Tournament Complete![/bold]")

        table = Table(title="Final Standings")
        table.add_column("Position", justify="center")
        table.add_column("Model", style="cyan")
        table.add_column("Final Stack", justify="right")
        table.add_column("Status")

        for standing in result.final_standings:
            model_short = standing["model"].split("/")[-1]
            position = standing["position"]

            if position == 1:
                pos_str = "[bold yellow]1st[/bold yellow]"
            elif position == 2:
                pos_str = "[bold white]2nd[/bold white]"
            elif position == 3:
                pos_str = "[bold]3rd[/bold]"
            else:
                pos_str = f"{position}th"

            if standing["eliminated_at"]:
                status = f"[red]Eliminated hand {standing['eliminated_at']}[/red]"
            else:
                status = "[green]Winner[/green]" if position == 1 else "[blue]Active[/blue]"

            table.add_row(
                pos_str,
                model_short,
                f"${standing['final_stack']:,}",
                status,
            )

        self.console.print(table)

        self.console.print(f"\nHands played: {result.hands_played}")
        self.console.print(f"Total tokens: {result.total_tokens:,}")
        self.console.print(f"Total cost: ${result.total_cost:.2f}")
