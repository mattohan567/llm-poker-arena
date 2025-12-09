"""ELO rating system for poker agents."""

import json
from dataclasses import dataclass
from pathlib import Path


# Default path for ELO data persistence
ELO_DATA_FILE = Path.home() / ".llm_poker" / "elo_ratings.json"


@dataclass
class EloRating:
    """ELO rating for a player."""
    model: str
    rating: int
    games_played: int
    wins: int
    losses: int
    draws: int


class EloSystem:
    """
    ELO rating system for poker agents.

    Uses standard ELO formula with K-factor adjustment based on games played.
    """

    # K-factor settings
    K_NEW_PLAYER = 40  # Higher K for new players (first 30 games)
    K_NORMAL = 20  # Normal K-factor
    K_ESTABLISHED = 10  # Lower K for established players (100+ games)

    # Starting rating
    DEFAULT_RATING = 1500

    def __init__(self):
        """Initialize ELO system."""
        self.ratings: dict[str, EloRating] = {}

    def get_rating(self, model: str) -> EloRating:
        """Get or create rating for a model."""
        if model not in self.ratings:
            self.ratings[model] = EloRating(
                model=model,
                rating=self.DEFAULT_RATING,
                games_played=0,
                wins=0,
                losses=0,
                draws=0,
            )
        return self.ratings[model]

    def update_ratings(
        self,
        winner: str,
        loser: str,
        draw: bool = False,
    ) -> tuple[int, int]:
        """
        Update ratings after a match.

        Args:
            winner: Model that won (or first player if draw)
            loser: Model that lost (or second player if draw)
            draw: Whether the match was a draw

        Returns:
            Tuple of (winner_new_rating, loser_new_rating)
        """
        winner_elo = self.get_rating(winner)
        loser_elo = self.get_rating(loser)

        # Calculate expected scores
        expected_winner = self._expected_score(winner_elo.rating, loser_elo.rating)
        expected_loser = self._expected_score(loser_elo.rating, winner_elo.rating)

        # Actual scores
        if draw:
            actual_winner = 0.5
            actual_loser = 0.5
        else:
            actual_winner = 1.0
            actual_loser = 0.0

        # Get K-factors
        k_winner = self._get_k_factor(winner_elo.games_played)
        k_loser = self._get_k_factor(loser_elo.games_played)

        # Calculate new ratings
        winner_new = winner_elo.rating + k_winner * (actual_winner - expected_winner)
        loser_new = loser_elo.rating + k_loser * (actual_loser - expected_loser)

        # Update ratings
        winner_elo.rating = int(round(winner_new))
        loser_elo.rating = int(round(loser_new))

        # Update game counts
        winner_elo.games_played += 1
        loser_elo.games_played += 1

        if draw:
            winner_elo.draws += 1
            loser_elo.draws += 1
        else:
            winner_elo.wins += 1
            loser_elo.losses += 1

        return winner_elo.rating, loser_elo.rating

    def _expected_score(self, rating_a: int, rating_b: int) -> float:
        """
        Calculate expected score for player A against player B.

        Uses the standard ELO formula:
        E_a = 1 / (1 + 10^((R_b - R_a) / 400))
        """
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    def _get_k_factor(self, games_played: int) -> int:
        """
        Get K-factor based on number of games played.

        New players have higher K for faster adjustment.
        Established players have lower K for stability.
        """
        if games_played < 30:
            return self.K_NEW_PLAYER
        elif games_played < 100:
            return self.K_NORMAL
        else:
            return self.K_ESTABLISHED

    def get_leaderboard(self) -> list[EloRating]:
        """Get all ratings sorted by ELO (descending)."""
        return sorted(
            self.ratings.values(),
            key=lambda x: x.rating,
            reverse=True,
        )

    def get_win_probability(self, model_a: str, model_b: str) -> float:
        """
        Get expected win probability for model_a against model_b.

        Returns probability between 0 and 1.
        """
        rating_a = self.get_rating(model_a).rating
        rating_b = self.get_rating(model_b).rating
        return self._expected_score(rating_a, rating_b)

    def load_ratings(self, ratings_data: list[dict]):
        """Load ratings from stored data."""
        for data in ratings_data:
            self.ratings[data["model"]] = EloRating(
                model=data["model"],
                rating=data["rating"],
                games_played=data.get("games_played", 0),
                wins=data.get("wins", 0),
                losses=data.get("losses", 0),
                draws=data.get("draws", 0),
            )

    def export_ratings(self) -> list[dict]:
        """Export ratings to storable format."""
        return [
            {
                "model": r.model,
                "rating": r.rating,
                "games_played": r.games_played,
                "wins": r.wins,
                "losses": r.losses,
                "draws": r.draws,
            }
            for r in self.ratings.values()
        ]

    def save_to_file(self, filepath: Path = ELO_DATA_FILE) -> None:
        """Save ratings to a JSON file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(self.export_ratings(), f, indent=2)

    def load_from_file(self, filepath: Path = ELO_DATA_FILE) -> None:
        """Load ratings from a JSON file if it exists."""
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
                self.load_ratings(data)


# Global ELO system instance
elo_system = EloSystem()
# Load existing ratings on import
elo_system.load_from_file()
