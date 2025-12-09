"""Game state wrapper around pokerkit for No-Limit Texas Hold'em."""

from dataclasses import dataclass
from typing import Any
import random

from pokerkit import Automation, NoLimitTexasHoldem


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    action_type: str
    amount: int | None = None
    error: str | None = None


@dataclass
class LegalAction:
    """A legal action a player can take."""
    action_type: str  # "fold", "check", "call", "raise"
    amount: int | None = None  # For call/raise
    min_raise: int | None = None  # For raise
    max_raise: int | None = None  # For raise (all-in)


@dataclass
class PlayerState:
    """State of a single player."""
    player_index: int
    model_name: str
    stack: int
    hole_cards: str | None  # None if not dealt or censored
    is_active: bool  # Still in hand
    current_bet: int


@dataclass
class GameStateSnapshot:
    """Snapshot of game state for LLM prompt."""
    pot: int
    community_cards: str
    current_player_index: int
    players: list[PlayerState]
    street: str  # "preflop", "flop", "turn", "river"
    betting_history: list[dict]
    legal_actions: list[LegalAction]
    amount_to_call: int
    min_raise: int | None
    max_raise: int | None


class GameStateWrapper:
    """Clean abstraction over pokerkit's State object for No-Limit Hold'em."""

    STREETS = ["preflop", "flop", "turn", "river"]

    # Automations for pokerkit - handle bookkeeping automatically
    AUTOMATIONS = (
        Automation.ANTE_POSTING,
        Automation.BET_COLLECTION,
        Automation.BLIND_OR_STRADDLE_POSTING,
        Automation.CARD_BURNING,
        Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
        Automation.HAND_KILLING,
        Automation.CHIPS_PUSHING,
        Automation.CHIPS_PULLING,
    )

    def __init__(
        self,
        player_models: list[str],
        starting_stacks: list[int],
        small_blind: int,
        big_blind: int,
        ante: int = 0,
    ):
        """
        Initialize a new No-Limit Hold'em game.

        Args:
            player_models: List of model names for each player
            starting_stacks: Starting chip stack for each player
            small_blind: Small blind amount
            big_blind: Big blind amount
            ante: Ante amount (default 0)
        """
        self.player_models = player_models
        self.num_players = len(player_models)
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.ante = ante

        # Create pokerkit state using positional arguments
        # Order: automations, ante_trimming_status, ante, blinds_or_straddles, min_bet, starting_stacks, player_count
        self.state = NoLimitTexasHoldem.create_state(
            self.AUTOMATIONS,
            True,  # ante_trimming_status (True = uniform antes)
            ante,  # ante amount
            (small_blind, big_blind),  # blinds_or_straddles
            big_blind,  # min_bet
            tuple(starting_stacks),  # starting_stacks
            self.num_players,  # player_count
        )

        # Track betting history
        self.betting_history: list[dict] = []
        self._current_street = "preflop"

        # Track dealt cards for logging
        self._hole_cards: dict[int, str] = {}
        self._community_cards: list[str] = []

    @classmethod
    def create_game(
        cls,
        player_models: list[str],
        starting_stack: int = 1_500_000,
        small_blind: int = 5_000,
        big_blind: int = 10_000,
        ante: int = 0,
    ) -> "GameStateWrapper":
        """
        Factory method to create a new game with uniform starting stacks.

        Args:
            player_models: List of model names for each player
            starting_stack: Starting stack for all players
            small_blind: Small blind amount
            big_blind: Big blind amount
            ante: Ante amount

        Returns:
            New GameStateWrapper instance
        """
        starting_stacks = [starting_stack] * len(player_models)
        return cls(player_models, starting_stacks, small_blind, big_blind, ante)

    def deal_hole_cards(self) -> dict[int, str]:
        """
        Deal hole cards to all players.

        Returns:
            Dict mapping player index to their hole cards string (e.g., "AsKh")
        """
        # Get cards that can be dealt
        dealable = list(self.state.get_dealable_cards())
        random.shuffle(dealable)

        card_idx = 0
        self._hole_cards = {}

        # Deal 2 cards to each active player
        for _ in range(2):  # Two cards per player
            for player_idx in range(self.num_players):
                if self.state.statuses[player_idx]:  # Player is active
                    card = dealable[card_idx]
                    card_str = repr(card)  # Use repr for short format like "As"
                    self.state.deal_hole(card_str)

                    if player_idx not in self._hole_cards:
                        self._hole_cards[player_idx] = card_str
                    else:
                        self._hole_cards[player_idx] += card_str

                    card_idx += 1

        return self._hole_cards.copy()

    def deal_community_cards(self, count: int) -> list[str]:
        """
        Deal community cards (flop=3, turn=1, river=1).

        Args:
            count: Number of cards to deal

        Returns:
            List of card strings dealt
        """
        dealable = list(self.state.get_dealable_cards())
        random.shuffle(dealable)

        cards_dealt = []
        cards_str = ""

        for i in range(count):
            card = dealable[i]
            card_str = repr(card)  # Use repr for short format like "As"
            cards_str += card_str
            cards_dealt.append(card_str)
            self._community_cards.append(card_str)

        self.state.deal_board(cards_str)

        # Update street
        if count == 3:
            self._current_street = "flop"
        elif self._current_street == "flop":
            self._current_street = "turn"
        elif self._current_street == "turn":
            self._current_street = "river"

        return cards_dealt

    def get_current_actor(self) -> int | None:
        """
        Get the index of the player who needs to act.

        Returns:
            Player index or None if no action needed
        """
        if not self.state.status:
            return None

        # Check if we're in a betting round
        actor = self.state.actor_index
        return actor

    def get_legal_actions(self) -> list[LegalAction]:
        """
        Get list of legal actions for the current actor.

        Returns:
            List of LegalAction objects
        """
        actions = []

        if self.state.actor_index is None:
            return actions

        # Always can fold when it's our turn to act
        actions.append(LegalAction(action_type="fold"))

        # Check if we can check or call
        if self.state.can_check_or_call():
            call_amount = self.state.checking_or_calling_amount or 0
            if call_amount == 0:
                actions.append(LegalAction(action_type="check"))
            else:
                actions.append(LegalAction(action_type="call", amount=call_amount))

        # Check if we can raise
        if self.state.can_complete_bet_or_raise_to():
            min_raise = self.state.min_completion_betting_or_raising_to_amount
            max_raise = self.state.max_completion_betting_or_raising_to_amount

            actions.append(LegalAction(
                action_type="raise",
                min_raise=min_raise,
                max_raise=max_raise,
            ))

        return actions

    def execute_action(self, action: dict) -> ActionResult:
        """
        Execute a player action.

        Args:
            action: Dict with "type" and optionally "amount"
                   e.g., {"type": "fold"}, {"type": "call"}, {"type": "raise", "amount": 50000}

        Returns:
            ActionResult with success status and details
        """
        action_type = action.get("type", "").lower()
        amount = action.get("amount")
        actor = self.state.actor_index

        try:
            if action_type == "fold":
                self.state.fold()
                self._record_action(actor, "fold", 0)
                return ActionResult(success=True, action_type="fold")

            elif action_type in ("check", "call"):
                call_amount = self.state.checking_or_calling_amount or 0
                self.state.check_or_call()
                actual_type = "check" if call_amount == 0 else "call"
                self._record_action(actor, actual_type, call_amount)
                return ActionResult(success=True, action_type=actual_type, amount=call_amount)

            elif action_type == "raise":
                if amount is None:
                    # Default to min raise
                    amount = self.state.min_completion_betting_or_raising_to_amount

                # Clamp to valid range
                min_raise = self.state.min_completion_betting_or_raising_to_amount
                max_raise = self.state.max_completion_betting_or_raising_to_amount
                amount = max(min_raise, min(amount, max_raise))

                self.state.complete_bet_or_raise_to(amount)
                self._record_action(actor, "raise", amount)
                return ActionResult(success=True, action_type="raise", amount=amount)

            else:
                return ActionResult(
                    success=False,
                    action_type=action_type,
                    error=f"Unknown action type: {action_type}"
                )

        except Exception as e:
            return ActionResult(
                success=False,
                action_type=action_type,
                error=str(e)
            )

    def _record_action(self, player_index: int, action_type: str, amount: int):
        """Record an action in the betting history."""
        self.betting_history.append({
            "player": player_index,
            "model": self.player_models[player_index],
            "action": action_type,
            "amount": amount,
            "street": self._current_street,
        })

    def is_betting_round_complete(self) -> bool:
        """Check if the current betting round is complete."""
        return self.state.actor_index is None and self.state.status

    def is_hand_complete(self) -> bool:
        """Check if the hand is finished."""
        return not self.state.status

    def get_active_player_count(self) -> int:
        """Get number of players still in the hand."""
        return sum(1 for s in self.state.statuses if s)

    def get_winners(self) -> list[dict]:
        """
        Get winners and their winnings after hand completes.

        Returns:
            List of dicts with player_index, model, and winnings
        """
        if not self.is_hand_complete():
            return []

        winners = []
        for i, payoff in enumerate(self.state.payoffs):
            if payoff > 0:
                winners.append({
                    "player_index": i,
                    "model": self.player_models[i],
                    "winnings": payoff,
                })

        return winners

    def get_state_for_player(self, player_index: int) -> GameStateSnapshot:
        """
        Get game state from a specific player's perspective.
        Censors other players' hole cards.

        Args:
            player_index: Index of the player

        Returns:
            GameStateSnapshot with all relevant information
        """
        players = []
        for i in range(self.num_players):
            # Only show hole cards for the requesting player
            hole_cards = None
            if i == player_index and i in self._hole_cards:
                hole_cards = self._hole_cards[i]

            players.append(PlayerState(
                player_index=i,
                model_name=self.player_models[i],
                stack=self.state.stacks[i],
                hole_cards=hole_cards,
                is_active=self.state.statuses[i],
                current_bet=self.state.bets[i] if self.state.bets else 0,
            ))

        # Get community cards
        community_cards = "".join(self._community_cards)

        # Get legal actions
        legal_actions = []
        amount_to_call = 0
        min_raise = None
        max_raise = None

        if self.state.actor_index == player_index:
            legal_actions = self.get_legal_actions()
            amount_to_call = self.state.checking_or_calling_amount or 0
            if self.state.can_complete_bet_or_raise_to():
                min_raise = self.state.min_completion_betting_or_raising_to_amount
                max_raise = self.state.max_completion_betting_or_raising_to_amount

        return GameStateSnapshot(
            pot=self.state.total_pot_amount,
            community_cards=community_cards,
            current_player_index=self.state.actor_index or -1,
            players=players,
            street=self._current_street,
            betting_history=self.betting_history.copy(),
            legal_actions=legal_actions,
            amount_to_call=amount_to_call,
            min_raise=min_raise,
            max_raise=max_raise,
        )

    def get_stacks(self) -> list[int]:
        """Get current stack sizes for all players."""
        return list(self.state.stacks)

    def get_pot(self) -> int:
        """Get current pot size."""
        return self.state.total_pot_amount

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize full state for logging.

        Returns:
            Dict with complete game state
        """
        return {
            "player_models": self.player_models,
            "num_players": self.num_players,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "ante": self.ante,
            "stacks": list(self.state.stacks),
            "pot": self.state.total_pot_amount,
            "hole_cards": self._hole_cards.copy(),
            "community_cards": self._community_cards.copy(),
            "street": self._current_street,
            "betting_history": self.betting_history.copy(),
            "is_complete": self.is_hand_complete(),
            "active_players": [i for i, s in enumerate(self.state.statuses) if s],
            "payoffs": list(self.state.payoffs) if self.is_hand_complete() else None,
        }

    def format_cards(self, cards: str) -> str:
        """
        Format card string for display.
        e.g., "AsKh" -> "A♠ K♥"
        """
        suit_map = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
        result = []

        for i in range(0, len(cards), 2):
            if i + 1 < len(cards):
                rank = cards[i].upper()
                suit = suit_map.get(cards[i + 1].lower(), cards[i + 1])
                result.append(f"{rank}{suit}")

        return " ".join(result)
