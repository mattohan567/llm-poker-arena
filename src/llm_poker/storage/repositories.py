"""Repository classes for database operations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from llm_poker.storage.supabase_client import get_supabase_client
from llm_poker.storage.models import (
    Tournament, TournamentCreate,
    Participant, ParticipantCreate,
    Hand, HandCreate,
    HandParticipant, HandParticipantCreate,
    Decision, DecisionCreate,
    ModelStats, MatchupStats,
)


class TournamentRepository:
    """Repository for tournament operations."""

    TABLE = "tournaments"

    def create(self, data: TournamentCreate) -> Tournament:
        """Create a new tournament."""
        client = get_supabase_client()
        result = client.table(self.TABLE).insert({
            "tournament_type": data.tournament_type,
            "config": data.config,
            "status": "pending",
        }).execute()

        return Tournament(**result.data[0])

    def get(self, tournament_id: UUID) -> Tournament | None:
        """Get tournament by ID."""
        client = get_supabase_client()
        result = client.table(self.TABLE).select("*").eq("id", str(tournament_id)).execute()

        if result.data:
            return Tournament(**result.data[0])
        return None

    def update_status(self, tournament_id: UUID, status: str) -> Tournament:
        """Update tournament status."""
        client = get_supabase_client()
        update_data = {"status": status}

        if status == "completed":
            update_data["completed_at"] = datetime.utcnow().isoformat()

        result = client.table(self.TABLE).update(update_data).eq("id", str(tournament_id)).execute()

        return Tournament(**result.data[0])

    def list_recent(self, limit: int = 10) -> list[Tournament]:
        """List recent tournaments."""
        client = get_supabase_client()
        result = client.table(self.TABLE).select("*").order("created_at", desc=True).limit(limit).execute()

        return [Tournament(**row) for row in result.data]


class ParticipantRepository:
    """Repository for tournament participant operations."""

    TABLE = "tournament_participants"

    def create(self, data: ParticipantCreate) -> Participant:
        """Create a tournament participant."""
        client = get_supabase_client()
        result = client.table(self.TABLE).insert({
            "tournament_id": str(data.tournament_id),
            "model_name": data.model_name,
            "seat_position": data.seat_position,
            "starting_stack": data.starting_stack,
        }).execute()

        return Participant(**result.data[0])

    def create_many(self, participants: list[ParticipantCreate]) -> list[Participant]:
        """Create multiple participants at once."""
        client = get_supabase_client()
        data = [
            {
                "tournament_id": str(p.tournament_id),
                "model_name": p.model_name,
                "seat_position": p.seat_position,
                "starting_stack": p.starting_stack,
            }
            for p in participants
        ]
        result = client.table(self.TABLE).insert(data).execute()

        return [Participant(**row) for row in result.data]

    def get_by_tournament(self, tournament_id: UUID) -> list[Participant]:
        """Get all participants in a tournament."""
        client = get_supabase_client()
        result = client.table(self.TABLE).select("*").eq("tournament_id", str(tournament_id)).order("seat_position").execute()

        return [Participant(**row) for row in result.data]

    def update_final_results(
        self,
        participant_id: UUID,
        final_stack: int,
        final_position: int | None = None,
        total_hands: int | None = None,
    ) -> Participant:
        """Update participant's final results."""
        client = get_supabase_client()
        update_data = {"final_stack": final_stack}

        if final_position is not None:
            update_data["final_position"] = final_position
        if total_hands is not None:
            update_data["total_hands_played"] = total_hands

        result = client.table(self.TABLE).update(update_data).eq("id", str(participant_id)).execute()

        return Participant(**result.data[0])


class HandRepository:
    """Repository for hand operations."""

    TABLE = "hands"
    PARTICIPANTS_TABLE = "hand_participants"

    def create(self, data: HandCreate) -> Hand:
        """Create a new hand record."""
        client = get_supabase_client()
        result = client.table(self.TABLE).insert({
            "tournament_id": str(data.tournament_id),
            "hand_number": data.hand_number,
            "small_blind": data.small_blind,
            "big_blind": data.big_blind,
        }).execute()

        return Hand(**result.data[0])

    def update_results(
        self,
        hand_id: UUID,
        pot_size: int,
        board_cards: str | None,
        winner_ids: list[UUID],
        hand_history: dict[str, Any],
    ) -> Hand:
        """Update hand with final results."""
        client = get_supabase_client()
        result = client.table(self.TABLE).update({
            "pot_size": pot_size,
            "board_cards": board_cards,
            "winner_ids": [str(w) for w in winner_ids],
            "hand_history": hand_history,
        }).eq("id", str(hand_id)).execute()

        return Hand(**result.data[0])

    def create_participant(self, data: HandParticipantCreate) -> HandParticipant:
        """Create a hand participant record."""
        client = get_supabase_client()
        result = client.table(self.PARTICIPANTS_TABLE).insert({
            "hand_id": str(data.hand_id),
            "participant_id": str(data.participant_id),
            "hole_cards": data.hole_cards,
            "starting_stack": data.starting_stack,
            "ending_stack": data.ending_stack,
            "profit_loss": data.profit_loss,
            "position": data.position,
            "went_to_showdown": data.went_to_showdown,
            "won_hand": data.won_hand,
        }).execute()

        return HandParticipant(**result.data[0])

    def get_hands_by_tournament(self, tournament_id: UUID, limit: int = 100) -> list[Hand]:
        """Get hands for a tournament."""
        client = get_supabase_client()
        result = client.table(self.TABLE).select("*").eq("tournament_id", str(tournament_id)).order("hand_number").limit(limit).execute()

        return [Hand(**row) for row in result.data]


class DecisionRepository:
    """Repository for decision operations."""

    TABLE = "decisions"

    def create(self, data: DecisionCreate) -> Decision:
        """Create a decision record."""
        client = get_supabase_client()
        result = client.table(self.TABLE).insert({
            "hand_id": str(data.hand_id),
            "participant_id": str(data.participant_id),
            "decision_number": data.decision_number,
            "street": data.street,
            "game_state": data.game_state,
            "prompt_messages": data.prompt_messages,
            "llm_response": data.llm_response,
            "tools_called": data.tools_called,
            "action_type": data.action_type,
            "action_amount": data.action_amount,
            "parse_success": data.parse_success,
            "parse_error": data.parse_error,
            "default_action_used": data.default_action_used,
            "latency_ms": data.latency_ms,
            "prompt_tokens": data.prompt_tokens,
            "completion_tokens": data.completion_tokens,
            "total_tokens": data.total_tokens,
            "cost_usd": data.cost_usd,
            "pot_odds": data.pot_odds,
            "equity_estimate": data.equity_estimate,
        }).execute()

        return Decision(**result.data[0])

    def get_by_hand(self, hand_id: UUID) -> list[Decision]:
        """Get all decisions for a hand."""
        client = get_supabase_client()
        result = client.table(self.TABLE).select("*").eq("hand_id", str(hand_id)).order("decision_number").execute()

        return [Decision(**row) for row in result.data]

    def get_by_participant(self, participant_id: UUID, limit: int = 100) -> list[Decision]:
        """Get decisions by participant."""
        client = get_supabase_client()
        result = client.table(self.TABLE).select("*").eq("participant_id", str(participant_id)).order("created_at", desc=True).limit(limit).execute()

        return [Decision(**row) for row in result.data]


class StatsRepository:
    """Repository for statistics operations."""

    MODEL_STATS_TABLE = "model_stats"
    MATCHUP_TABLE = "matchup_stats"

    def get_or_create_model_stats(
        self,
        model_name: str,
        tournament_id: UUID,
    ) -> ModelStats:
        """Get or create model stats for a tournament."""
        client = get_supabase_client()

        # Try to get existing
        result = client.table(self.MODEL_STATS_TABLE).select("*").eq("model_name", model_name).eq("tournament_id", str(tournament_id)).execute()

        if result.data:
            return ModelStats(**result.data[0])

        # Create new
        result = client.table(self.MODEL_STATS_TABLE).insert({
            "model_name": model_name,
            "tournament_id": str(tournament_id),
        }).execute()

        return ModelStats(**result.data[0])

    def update_model_stats(
        self,
        stats_id: UUID,
        updates: dict[str, Any],
    ) -> ModelStats:
        """Update model statistics."""
        client = get_supabase_client()
        updates["updated_at"] = datetime.utcnow().isoformat()

        result = client.table(self.MODEL_STATS_TABLE).update(updates).eq("id", str(stats_id)).execute()

        return ModelStats(**result.data[0])

    def get_leaderboard(self, limit: int = 20) -> list[ModelStats]:
        """Get leaderboard sorted by ELO."""
        client = get_supabase_client()
        result = client.table(self.MODEL_STATS_TABLE).select("*").order("elo_rating", desc=True).limit(limit).execute()

        return [ModelStats(**row) for row in result.data]

    def get_or_create_matchup(self, model_a: str, model_b: str) -> MatchupStats:
        """Get or create matchup stats between two models."""
        client = get_supabase_client()

        # Normalize ordering (alphabetical)
        if model_a > model_b:
            model_a, model_b = model_b, model_a

        # Try to get existing
        result = client.table(self.MATCHUP_TABLE).select("*").eq("model_a", model_a).eq("model_b", model_b).execute()

        if result.data:
            return MatchupStats(**result.data[0])

        # Create new
        result = client.table(self.MATCHUP_TABLE).insert({
            "model_a": model_a,
            "model_b": model_b,
        }).execute()

        return MatchupStats(**result.data[0])

    def update_matchup(
        self,
        matchup_id: UUID,
        updates: dict[str, Any],
    ) -> MatchupStats:
        """Update matchup statistics."""
        client = get_supabase_client()
        updates["updated_at"] = datetime.utcnow().isoformat()

        result = client.table(self.MATCHUP_TABLE).update(updates).eq("id", str(matchup_id)).execute()

        return MatchupStats(**result.data[0])
