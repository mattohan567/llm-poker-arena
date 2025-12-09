"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field


# --- Leaderboard Schemas ---

class EloRatingResponse(BaseModel):
    """Single player ELO rating."""

    model: str
    rating: int
    games_played: int
    wins: int
    losses: int
    draws: int
    win_rate: float = Field(description="Win percentage (0-100)")

    class Config:
        json_schema_extra = {
            "example": {
                "model": "openai/gpt-4o",
                "rating": 1520,
                "games_played": 10,
                "wins": 7,
                "losses": 3,
                "draws": 0,
                "win_rate": 70.0,
            }
        }


class LeaderboardResponse(BaseModel):
    """Full leaderboard response."""

    rankings: list[EloRatingResponse]
    total_models: int
    last_updated: datetime | None = None


# --- Models Schemas ---

class ModelInfo(BaseModel):
    """Information about an available model."""

    id: str = Field(description="Full model identifier (provider/model-name)")
    provider: str
    name: str
    configured: bool = Field(description="Whether API key is configured")


class ModelsListResponse(BaseModel):
    """List of available models."""

    models: list[ModelInfo]
    total: int


# --- Match Schemas ---

class MatchCreateRequest(BaseModel):
    """Request to create a new heads-up match."""

    model1: str = Field(description="First model (e.g., openai/gpt-4o)")
    model2: str = Field(description="Second model")
    num_hands: int = Field(default=10, ge=1, le=1000)
    starting_stack: int = Field(default=1_500_000, ge=10_000)
    small_blind: int = Field(default=5_000, ge=100)
    big_blind: int = Field(default=10_000, ge=200)

    class Config:
        json_schema_extra = {
            "example": {
                "model1": "openai/gpt-4o",
                "model2": "anthropic/claude-sonnet-4-20250514",
                "num_hands": 10,
                "starting_stack": 1500000,
                "small_blind": 5000,
                "big_blind": 10000,
            }
        }


class PlayerResult(BaseModel):
    """Result for a single player in a match."""

    model: str
    final_stack: int
    profit_loss: int
    is_winner: bool


class MatchResult(BaseModel):
    """Result of a completed match."""

    id: str
    model1: str
    model2: str
    hands_played: int
    winner: str | None
    player_results: list[PlayerResult]
    total_tokens: int
    total_cost: float
    duration_seconds: float | None = None
    created_at: datetime


class MatchStatus(BaseModel):
    """Status of a match (for async matches)."""

    id: str
    status: str = Field(description="pending, running, completed, failed")
    hands_completed: int = 0
    total_hands: int
    current_hand: int | None = None
    error: str | None = None


class MatchListResponse(BaseModel):
    """List of matches."""

    matches: list[MatchResult]
    total: int
    page: int = 1
    per_page: int = 20


# --- Health Check ---

class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    supabase_connected: bool
    models_configured: int
