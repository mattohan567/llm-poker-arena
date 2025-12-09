"""Tests for ELO rating system."""

import pytest
from llm_poker.analytics.elo import EloSystem, EloRating


class TestEloSystem:
    """Tests for EloSystem."""

    @pytest.fixture
    def elo_system(self):
        """Fresh ELO system for each test."""
        return EloSystem()

    def test_initial_rating(self, elo_system):
        """Test that new players start at default rating."""
        rating = elo_system.get_rating("test/model")

        assert rating.rating == 1500
        assert rating.games_played == 0

    def test_update_ratings_winner_gains(self, elo_system):
        """Test that winner gains rating points."""
        winner_before = elo_system.get_rating("winner/model").rating
        loser_before = elo_system.get_rating("loser/model").rating

        elo_system.update_ratings("winner/model", "loser/model")

        winner_after = elo_system.get_rating("winner/model").rating
        loser_after = elo_system.get_rating("loser/model").rating

        assert winner_after > winner_before
        assert loser_after < loser_before

    def test_update_ratings_draw(self, elo_system):
        """Test that draw doesn't change ratings much for equal players."""
        elo_system.update_ratings("model/a", "model/b", draw=True)

        rating_a = elo_system.get_rating("model/a").rating
        rating_b = elo_system.get_rating("model/b").rating

        # Should be roughly equal
        assert abs(rating_a - rating_b) < 5

    def test_upset_victory_larger_change(self, elo_system):
        """Test that upset victories cause larger rating changes."""
        # First, give one player a higher rating
        for _ in range(5):
            elo_system.update_ratings("strong/model", "weak/model")

        strong_before = elo_system.get_rating("strong/model").rating
        weak_before = elo_system.get_rating("weak/model").rating

        # Upset: weak beats strong
        elo_system.update_ratings("weak/model", "strong/model")

        strong_after = elo_system.get_rating("strong/model").rating
        weak_after = elo_system.get_rating("weak/model").rating

        # Weak player should gain significantly
        weak_gain = weak_after - weak_before
        assert weak_gain > 20  # Should be a big gain

    def test_win_probability(self, elo_system):
        """Test win probability calculation."""
        # Equal ratings = 50% each
        prob = elo_system.get_win_probability("model/a", "model/b")
        assert abs(prob - 0.5) < 0.01

        # Give one player higher rating
        elo_system.update_ratings("model/a", "model/b")
        elo_system.update_ratings("model/a", "model/b")

        # Now model/a should have higher win probability
        prob_a = elo_system.get_win_probability("model/a", "model/b")
        assert prob_a > 0.5

    def test_leaderboard_sorted(self, elo_system):
        """Test that leaderboard is sorted by rating."""
        # Create some players with different ratings
        elo_system.update_ratings("top/model", "mid/model")
        elo_system.update_ratings("top/model", "bottom/model")
        elo_system.update_ratings("mid/model", "bottom/model")

        leaderboard = elo_system.get_leaderboard()

        # Should be sorted descending by rating
        ratings = [r.rating for r in leaderboard]
        assert ratings == sorted(ratings, reverse=True)

    def test_export_import_ratings(self, elo_system):
        """Test exporting and importing ratings."""
        # Create some data
        elo_system.update_ratings("model/a", "model/b")
        elo_system.update_ratings("model/a", "model/c")

        # Export
        exported = elo_system.export_ratings()

        # Create new system and import
        new_system = EloSystem()
        new_system.load_ratings(exported)

        # Should have same ratings
        for model in ["model/a", "model/b", "model/c"]:
            assert new_system.get_rating(model).rating == elo_system.get_rating(model).rating
