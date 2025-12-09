"""Pydantic models for database entities."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TournamentCreate(BaseModel):
    """Data for creating a new tournament."""
    tournament_type: str  # "heads_up", "round_robin", "full_table"
    config: dict[str, Any]  # blinds, starting_stacks, etc.


class Tournament(BaseModel):
    """Tournament record from database."""
    id: UUID
    tournament_type: str
    created_at: datetime
    completed_at: datetime | None = None
    config: dict[str, Any]
    status: str = "pending"  # pending, running, completed, failed


class ParticipantCreate(BaseModel):
    """Data for creating a tournament participant."""
    tournament_id: UUID
    model_name: str
    seat_position: int
    starting_stack: int


class Participant(BaseModel):
    """Tournament participant record."""
    id: UUID
    tournament_id: UUID
    model_name: str
    seat_position: int
    starting_stack: int
    final_stack: int | None = None
    final_position: int | None = None
    total_hands_played: int = 0


class HandCreate(BaseModel):
    """Data for creating a new hand record."""
    tournament_id: UUID
    hand_number: int
    small_blind: int
    big_blind: int


class Hand(BaseModel):
    """Hand record from database."""
    id: UUID
    tournament_id: UUID
    hand_number: int
    created_at: datetime
    small_blind: int
    big_blind: int
    pot_size: int | None = None
    board_cards: str | None = None
    winner_ids: list[UUID] | None = None
    hand_history: dict[str, Any] | None = None


class HandParticipantCreate(BaseModel):
    """Data for creating a hand participant record."""
    hand_id: UUID
    participant_id: UUID
    hole_cards: str | None = None
    starting_stack: int
    ending_stack: int
    profit_loss: int
    position: str  # "BTN", "SB", "BB", "UTG", etc.
    went_to_showdown: bool = False
    won_hand: bool = False


class HandParticipant(BaseModel):
    """Per-player hand participation record."""
    id: UUID
    hand_id: UUID
    participant_id: UUID
    hole_cards: str | None = None
    starting_stack: int
    ending_stack: int
    profit_loss: int
    position: str
    went_to_showdown: bool = False
    won_hand: bool = False


class DecisionCreate(BaseModel):
    """Data for creating a decision record."""
    hand_id: UUID
    participant_id: UUID
    decision_number: int
    street: str  # "preflop", "flop", "turn", "river"
    game_state: dict[str, Any]
    prompt_messages: list[dict[str, Any]]
    llm_response: str | None = None
    tools_called: list[dict[str, Any]] | None = None
    action_type: str
    action_amount: int | None = None
    parse_success: bool = True
    parse_error: str | None = None
    default_action_used: bool = False
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    pot_odds: float | None = None
    equity_estimate: float | None = None


class Decision(BaseModel):
    """Decision record from database."""
    id: UUID
    hand_id: UUID
    participant_id: UUID
    decision_number: int
    street: str
    game_state: dict[str, Any]
    prompt_messages: list[dict[str, Any]]
    llm_response: str | None = None
    tools_called: list[dict[str, Any]] | None = None
    action_type: str
    action_amount: int | None = None
    parse_success: bool = True
    parse_error: str | None = None
    default_action_used: bool = False
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    pot_odds: float | None = None
    equity_estimate: float | None = None
    created_at: datetime


class ModelStatsCreate(BaseModel):
    """Data for creating/updating model stats."""
    model_name: str
    tournament_id: UUID


class ModelStats(BaseModel):
    """Aggregate statistics per model."""
    id: UUID
    model_name: str
    tournament_id: UUID

    # Win metrics
    hands_played: int = 0
    hands_won: int = 0
    showdowns_reached: int = 0
    showdowns_won: int = 0

    # Financial metrics
    total_profit_loss: int = 0
    biggest_pot_won: int = 0
    avg_profit_per_hand: float | None = None
    roi: float | None = None

    # Behavioral metrics
    vpip: float | None = None  # Voluntarily put in pot %
    pfr: float | None = None  # Pre-flop raise %
    aggression_factor: float | None = None
    fold_to_3bet: float | None = None
    cbet_frequency: float | None = None
    bluff_frequency: float | None = None

    # Tool usage
    tool_usage_rate: float | None = None
    pot_odds_compliance: float | None = None

    # Cost metrics
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: int | None = None
    parse_failure_rate: float | None = None

    # ELO
    elo_rating: int = 1500

    updated_at: datetime


class MatchupStats(BaseModel):
    """Head-to-head matchup statistics."""
    id: UUID
    model_a: str
    model_b: str
    hands_played: int = 0
    model_a_wins: int = 0
    model_b_wins: int = 0
    model_a_profit: int = 0
    model_b_profit: int = 0
    updated_at: datetime
