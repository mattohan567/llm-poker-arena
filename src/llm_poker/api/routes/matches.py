"""Matches API routes."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from llm_poker.analytics.elo import elo_system
from llm_poker.tournament.heads_up import HeadsUpMatch
from llm_poker.api.schemas import (
    MatchCreateRequest,
    MatchResult,
    MatchStatus,
    MatchListResponse,
    PlayerResult,
)

router = APIRouter(prefix="/matches", tags=["matches"])

# In-memory storage for match status (in production, use Redis or DB)
_match_store: dict[str, dict[str, Any]] = {}


@router.post("/heads-up", response_model=MatchStatus)
async def create_heads_up_match(
    request: MatchCreateRequest,
    background_tasks: BackgroundTasks,
) -> MatchStatus:
    """
    Start a new heads-up match between two models.

    The match runs asynchronously in the background.
    Use GET /matches/{id}/status to check progress.
    """
    match_id = str(uuid.uuid4())

    # Initialize match status
    _match_store[match_id] = {
        "id": match_id,
        "status": "pending",
        "hands_completed": 0,
        "total_hands": request.num_hands,
        "current_hand": None,
        "error": None,
        "result": None,
        "created_at": datetime.now(timezone.utc),
        "request": request,
    }

    # Run match in background
    background_tasks.add_task(_run_match, match_id, request)

    return MatchStatus(
        id=match_id,
        status="pending",
        hands_completed=0,
        total_hands=request.num_hands,
    )


async def _run_match(match_id: str, request: MatchCreateRequest) -> None:
    """Run a match in the background and update status."""
    try:
        _match_store[match_id]["status"] = "running"

        match = HeadsUpMatch(
            model1=request.model1,
            model2=request.model2,
            num_hands=request.num_hands,
            starting_stack=request.starting_stack,
            small_blind=request.small_blind,
            big_blind=request.big_blind,
            log_to_db=True,
        )

        start_time = datetime.now(timezone.utc)
        result = await match.run()
        end_time = datetime.now(timezone.utc)

        # Update ELO
        if result.winner:
            loser = request.model2 if result.winner == request.model1 else request.model1
            elo_system.update_ratings(result.winner, loser, draw=False)
            elo_system.save_to_file()

        # Store result
        _match_store[match_id]["status"] = "completed"
        _match_store[match_id]["hands_completed"] = result.hands_played
        _match_store[match_id]["result"] = MatchResult(
            id=match_id,
            model1=request.model1,
            model2=request.model2,
            hands_played=result.hands_played,
            winner=result.winner,
            player_results=[
                PlayerResult(
                    model=request.model1,
                    final_stack=result.model1_final_stack,
                    profit_loss=result.model1_profit,
                    is_winner=result.winner == request.model1,
                ),
                PlayerResult(
                    model=request.model2,
                    final_stack=result.model2_final_stack,
                    profit_loss=result.model2_profit,
                    is_winner=result.winner == request.model2,
                ),
            ],
            total_tokens=result.total_tokens,
            total_cost=result.total_cost,
            duration_seconds=(end_time - start_time).total_seconds(),
            created_at=_match_store[match_id]["created_at"],
        )

    except Exception as e:
        _match_store[match_id]["status"] = "failed"
        _match_store[match_id]["error"] = str(e)


@router.get("/{match_id}/status", response_model=MatchStatus)
async def get_match_status(match_id: str) -> MatchStatus:
    """
    Get the status of a match.

    Use this to poll for match completion.
    """
    if match_id not in _match_store:
        raise HTTPException(status_code=404, detail="Match not found")

    match_data = _match_store[match_id]

    return MatchStatus(
        id=match_id,
        status=match_data["status"],
        hands_completed=match_data["hands_completed"],
        total_hands=match_data["total_hands"],
        current_hand=match_data.get("current_hand"),
        error=match_data.get("error"),
    )


@router.get("/{match_id}", response_model=MatchResult)
async def get_match_result(match_id: str) -> MatchResult:
    """
    Get the full result of a completed match.

    Returns 404 if match not found, 400 if match not yet completed.
    """
    if match_id not in _match_store:
        raise HTTPException(status_code=404, detail="Match not found")

    match_data = _match_store[match_id]

    if match_data["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Match not completed. Status: {match_data['status']}",
        )

    return match_data["result"]


@router.get("", response_model=MatchListResponse)
async def list_matches(
    page: int = 1,
    per_page: int = 20,
) -> MatchListResponse:
    """
    List all matches (from in-memory store).

    Note: In production, this should query Supabase for persistent history.
    """
    completed_matches = [
        m["result"]
        for m in _match_store.values()
        if m["status"] == "completed" and m.get("result")
    ]

    # Sort by created_at descending
    completed_matches.sort(key=lambda x: x.created_at, reverse=True)

    # Pagination
    start = (page - 1) * per_page
    end = start + per_page
    paginated = completed_matches[start:end]

    return MatchListResponse(
        matches=paginated,
        total=len(completed_matches),
        page=page,
        per_page=per_page,
    )
