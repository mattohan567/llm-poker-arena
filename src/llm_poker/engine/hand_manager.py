"""Hand manager for orchestrating a single poker hand."""

from dataclasses import dataclass
from uuid import UUID

from llm_poker.engine.game_state import GameStateWrapper, GameStateSnapshot
from llm_poker.agents.poker_agent import PokerAgent, AgentResponse
from llm_poker.storage.models import (
    HandCreate, HandParticipantCreate, DecisionCreate,
)
from llm_poker.storage.repositories import HandRepository, DecisionRepository


@dataclass
class HandResult:
    """Result of a completed hand."""
    hand_number: int
    pot_size: int
    board_cards: str
    winners: list[dict]  # [{player_index, model, winnings}]
    player_results: list[dict]  # [{player_index, model, profit_loss, hole_cards}]
    decisions_count: int
    total_tokens: int
    total_cost: float


@dataclass
class DecisionLog:
    """Log of a single decision."""
    player_index: int
    model: str
    street: str
    action: dict
    response: AgentResponse
    game_state_snapshot: dict


class HandManager:
    """Manages the lifecycle of a single poker hand."""

    POSITION_NAMES_2P = ["BTN/SB", "BB"]
    POSITION_NAMES_6P = ["BTN", "SB", "BB", "UTG", "MP", "CO"]

    def __init__(
        self,
        agents: list[PokerAgent],
        starting_stacks: list[int],
        small_blind: int,
        big_blind: int,
        hand_number: int = 1,
        tournament_id: UUID | None = None,
        participant_ids: list[UUID] | None = None,
        log_to_db: bool = True,
    ):
        """
        Initialize hand manager.

        Args:
            agents: List of PokerAgent instances for each seat
            starting_stacks: Starting stack for each player
            small_blind: Small blind amount
            big_blind: Big blind amount
            hand_number: Hand number in the session/tournament
            tournament_id: Optional tournament ID for logging
            participant_ids: Optional participant IDs for logging
            log_to_db: Whether to log to database
        """
        self.agents = agents
        self.starting_stacks = starting_stacks
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.hand_number = hand_number
        self.tournament_id = tournament_id
        self.participant_ids = participant_ids or []
        self.log_to_db = log_to_db

        self.num_players = len(agents)
        self.model_names = [agent.model for agent in agents]

        # State tracking
        self.game_state: GameStateWrapper | None = None
        self.decision_logs: list[DecisionLog] = []
        self.decision_number = 0

        # Repositories
        self.hand_repo = HandRepository() if log_to_db else None
        self.decision_repo = DecisionRepository() if log_to_db else None

        # Database IDs
        self.hand_id: UUID | None = None

    async def play_hand(self) -> HandResult:
        """
        Execute a complete hand from deal to showdown.

        Returns:
            HandResult with complete hand information
        """
        # Initialize game state
        self.game_state = GameStateWrapper(
            player_models=self.model_names,
            starting_stacks=self.starting_stacks,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
        )

        # Create hand record in database
        if self.log_to_db and self.tournament_id:
            hand = self.hand_repo.create(HandCreate(
                tournament_id=self.tournament_id,
                hand_number=self.hand_number,
                small_blind=self.small_blind,
                big_blind=self.big_blind,
            ))
            self.hand_id = hand.id

        # Deal hole cards
        hole_cards = self.game_state.deal_hole_cards()

        # Run preflop betting
        hand_continues = await self._run_betting_round("preflop")

        # Flop
        if hand_continues and self.game_state.get_active_player_count() > 1:
            self.game_state.deal_community_cards(3)
            hand_continues = await self._run_betting_round("flop")

        # Turn
        if hand_continues and self.game_state.get_active_player_count() > 1:
            self.game_state.deal_community_cards(1)
            hand_continues = await self._run_betting_round("turn")

        # River
        if hand_continues and self.game_state.get_active_player_count() > 1:
            self.game_state.deal_community_cards(1)
            hand_continues = await self._run_betting_round("river")

        # Get results
        winners = self.game_state.get_winners()
        final_state = self.game_state.to_dict()

        # Calculate player results
        player_results = []
        for i in range(self.num_players):
            payoff = self.game_state.state.payoffs[i]
            player_results.append({
                "player_index": i,
                "model": self.model_names[i],
                "profit_loss": payoff,
                "hole_cards": hole_cards.get(i, ""),
                "starting_stack": self.starting_stacks[i],
                "ending_stack": self.starting_stacks[i] + payoff,
            })

        # Calculate totals
        total_tokens = sum(d.response.tokens.total_tokens for d in self.decision_logs)
        total_cost = sum(d.response.cost_usd for d in self.decision_logs)

        # Update hand record with results
        if self.log_to_db and self.hand_id:
            winner_ids = []
            if self.participant_ids:
                for w in winners:
                    if w["player_index"] < len(self.participant_ids):
                        winner_ids.append(self.participant_ids[w["player_index"]])

            self.hand_repo.update_results(
                hand_id=self.hand_id,
                pot_size=final_state["pot"],
                board_cards="".join(final_state["community_cards"]),
                winner_ids=winner_ids,
                hand_history=final_state,
            )

            # Create hand participant records
            if self.participant_ids:
                for i, result in enumerate(player_results):
                    if i < len(self.participant_ids):
                        position = self._get_position_name(i)
                        self.hand_repo.create_participant(HandParticipantCreate(
                            hand_id=self.hand_id,
                            participant_id=self.participant_ids[i],
                            hole_cards=result["hole_cards"],
                            starting_stack=result["starting_stack"],
                            ending_stack=result["ending_stack"],
                            profit_loss=result["profit_loss"],
                            position=position,
                            went_to_showdown=self.game_state.get_active_player_count() > 1,
                            won_hand=result["profit_loss"] > 0,
                        ))

        return HandResult(
            hand_number=self.hand_number,
            pot_size=final_state["pot"],
            board_cards="".join(final_state["community_cards"]),
            winners=winners,
            player_results=player_results,
            decisions_count=len(self.decision_logs),
            total_tokens=total_tokens,
            total_cost=total_cost,
        )

    async def _run_betting_round(self, street: str) -> bool:
        """
        Run a single betting round.

        Args:
            street: Current street name

        Returns:
            True if hand should continue, False if hand ended
        """
        while True:
            # Check if hand is complete
            if self.game_state.is_hand_complete():
                return False

            # Check if betting round is complete
            if self.game_state.is_betting_round_complete():
                return True

            # Get current actor
            actor_index = self.game_state.get_current_actor()
            if actor_index is None:
                return True

            # Check if only one player left
            if self.game_state.get_active_player_count() <= 1:
                return False

            # Get action from agent
            agent = self.agents[actor_index]
            game_snapshot = self.game_state.get_state_for_player(actor_index)

            # Convert snapshot to dict for agent
            state_dict = self._snapshot_to_dict(game_snapshot)

            # Get agent decision
            response = await agent.get_action(
                game_state=state_dict,
                player_index=actor_index,
                betting_history=self.game_state.betting_history,
            )

            # Execute action
            self.game_state.execute_action(response.action)

            # Log decision
            self.decision_number += 1
            log = DecisionLog(
                player_index=actor_index,
                model=self.model_names[actor_index],
                street=street,
                action=response.action,
                response=response,
                game_state_snapshot=state_dict,
            )
            self.decision_logs.append(log)

            # Save to database
            if self.log_to_db and self.hand_id and self.participant_ids:
                await self._log_decision(log)

    async def _log_decision(self, log: DecisionLog):
        """Log a decision to the database."""
        if log.player_index >= len(self.participant_ids):
            return

        # Extract tool usage info
        tools_called = None
        pot_odds = None
        equity_estimate = None

        if log.response.tool_calls:
            tools_called = log.response.tool_calls
            for tc in log.response.tool_calls:
                if tc.get("name") == "pot_odds_calculator":
                    result = tc.get("result", {})
                    pot_odds = result.get("pot_odds_percentage")
                elif tc.get("name") == "equity_calculator":
                    result = tc.get("result", {})
                    equity_estimate = result.get("equity_percentage")

        self.decision_repo.create(DecisionCreate(
            hand_id=self.hand_id,
            participant_id=self.participant_ids[log.player_index],
            decision_number=self.decision_number,
            street=log.street,
            game_state=log.game_state_snapshot,
            prompt_messages=[],  # Could store full messages if needed
            llm_response=log.response.raw_response,
            tools_called=tools_called,
            action_type=log.action.get("type", "unknown"),
            action_amount=log.action.get("amount"),
            parse_success=log.response.parse_success,
            parse_error=log.response.error,
            default_action_used=log.response.default_action_used,
            latency_ms=log.response.latency_ms,
            prompt_tokens=log.response.tokens.prompt_tokens,
            completion_tokens=log.response.tokens.completion_tokens,
            total_tokens=log.response.tokens.total_tokens,
            cost_usd=log.response.cost_usd,
            pot_odds=pot_odds,
            equity_estimate=equity_estimate,
        ))

    def _snapshot_to_dict(self, snapshot: GameStateSnapshot) -> dict:
        """Convert GameStateSnapshot to dict for agent."""
        return {
            "pot": snapshot.pot,
            "community_cards": snapshot.community_cards,
            "current_player_index": snapshot.current_player_index,
            "players": [
                {
                    "player_index": p.player_index,
                    "model_name": p.model_name,
                    "stack": p.stack,
                    "hole_cards": p.hole_cards,
                    "is_active": p.is_active,
                    "current_bet": p.current_bet,
                }
                for p in snapshot.players
            ],
            "street": snapshot.street,
            "betting_history": snapshot.betting_history,
            "legal_actions": [
                {
                    "action_type": a.action_type,
                    "amount": a.amount,
                    "min_raise": a.min_raise,
                    "max_raise": a.max_raise,
                }
                for a in snapshot.legal_actions
            ],
            "amount_to_call": snapshot.amount_to_call,
            "min_raise": snapshot.min_raise,
            "max_raise": snapshot.max_raise,
        }

    def _get_position_name(self, seat_index: int) -> str:
        """Get position name for a seat index."""
        if self.num_players == 2:
            return self.POSITION_NAMES_2P[seat_index % 2]
        elif self.num_players <= 6:
            positions = self.POSITION_NAMES_6P[:self.num_players]
            return positions[seat_index % len(positions)]
        else:
            return f"Seat{seat_index}"

    def get_decision_summary(self) -> list[dict]:
        """Get summary of all decisions in the hand."""
        return [
            {
                "decision_number": i + 1,
                "player": log.model,
                "street": log.street,
                "action": log.action,
                "latency_ms": log.response.latency_ms,
                "tokens": log.response.tokens.total_tokens,
                "cost": log.response.cost_usd,
                "tools_used": len(log.response.tool_calls) > 0,
                "parse_success": log.response.parse_success,
            }
            for i, log in enumerate(self.decision_logs)
        ]
