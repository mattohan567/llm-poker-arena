"""Leaderboard API routes."""

from datetime import datetime, timezone
from fastapi import APIRouter

from llm_poker.analytics.elo import elo_system
from llm_poker.api.schemas import EloRatingResponse, LeaderboardResponse

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=LeaderboardResponse)
async def get_leaderboard() -> LeaderboardResponse:
    """
    Get the current ELO leaderboard.

    Returns all models ranked by ELO rating with win/loss records.
    """
    ratings = elo_system.get_leaderboard()

    rankings = []
    for rating in ratings:
        win_rate = 0.0
        if rating.games_played > 0:
            win_rate = (rating.wins / rating.games_played) * 100

        rankings.append(
            EloRatingResponse(
                model=rating.model,
                rating=rating.rating,
                games_played=rating.games_played,
                wins=rating.wins,
                losses=rating.losses,
                draws=rating.draws,
                win_rate=round(win_rate, 1),
            )
        )

    return LeaderboardResponse(
        rankings=rankings,
        total_models=len(rankings),
        last_updated=datetime.now(timezone.utc) if rankings else None,
    )


@router.get("/{model_id:path}", response_model=EloRatingResponse)
async def get_model_rating(model_id: str) -> EloRatingResponse:
    """
    Get ELO rating for a specific model.

    Args:
        model_id: Model identifier (e.g., openai/gpt-4o)
    """
    rating = elo_system.get_rating(model_id)

    win_rate = 0.0
    if rating.games_played > 0:
        win_rate = (rating.wins / rating.games_played) * 100

    return EloRatingResponse(
        model=rating.model,
        rating=rating.rating,
        games_played=rating.games_played,
        wins=rating.wins,
        losses=rating.losses,
        draws=rating.draws,
        win_rate=round(win_rate, 1),
    )
