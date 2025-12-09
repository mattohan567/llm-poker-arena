"""Tests for poker tools."""

import pytest
from llm_poker.tools.pot_odds import calculate_pot_odds


class TestPotOddsCalculator:
    """Tests for pot odds calculator."""

    def test_basic_pot_odds(self):
        """Test basic pot odds calculation."""
        result = calculate_pot_odds(pot_size=300, bet_to_call=100)

        assert result["pot_odds_percentage"] == 25.0
        assert result["pot_odds_ratio"] == "3.0:1"
        assert result["break_even_equity"] == 25.0

    def test_zero_bet(self):
        """Test with no bet to call."""
        result = calculate_pot_odds(pot_size=100, bet_to_call=0)

        assert result["pot_odds_percentage"] == 0.0
        assert "free" in result["recommendation"].lower()

    def test_large_pot_odds(self):
        """Test with large pot giving good odds."""
        result = calculate_pot_odds(pot_size=1000, bet_to_call=100)

        # 100 / (1000 + 100) = 9.09%
        assert result["pot_odds_percentage"] < 10
        assert "excellent" in result["recommendation"].lower()

    def test_poor_pot_odds(self):
        """Test with poor pot odds."""
        result = calculate_pot_odds(pot_size=100, bet_to_call=200)

        # 200 / (100 + 200) = 66.7%
        assert result["pot_odds_percentage"] > 60
        assert "poor" in result["recommendation"].lower()
