"""Tests for action parser."""

import pytest
from llm_poker.agents.action_parser import ActionParser


class TestActionParser:
    """Tests for ActionParser."""

    @pytest.fixture
    def legal_actions_all(self):
        """All actions legal."""
        return [
            {"action_type": "fold"},
            {"action_type": "check"},
            {"action_type": "call", "amount": 100},
            {"action_type": "raise", "min_raise": 200, "max_raise": 1000},
        ]

    @pytest.fixture
    def legal_actions_no_check(self):
        """Can't check (facing a bet)."""
        return [
            {"action_type": "fold"},
            {"action_type": "call", "amount": 100},
            {"action_type": "raise", "min_raise": 200, "max_raise": 1000},
        ]

    def test_parse_fold(self, legal_actions_all):
        """Test parsing FOLD action."""
        result = ActionParser.parse("I will FOLD this hand.", legal_actions_all)

        assert result.success
        assert result.action_type == "fold"

    def test_parse_check(self, legal_actions_all):
        """Test parsing CHECK action."""
        result = ActionParser.parse("Let me CHECK here.", legal_actions_all)

        assert result.success
        assert result.action_type == "check"

    def test_parse_call(self, legal_actions_no_check):
        """Test parsing CALL action."""
        result = ActionParser.parse("I CALL the bet.", legal_actions_no_check)

        assert result.success
        assert result.action_type == "call"

    def test_parse_raise_with_amount(self, legal_actions_all):
        """Test parsing RAISE with amount."""
        result = ActionParser.parse("I will RAISE 500.", legal_actions_all)

        assert result.success
        assert result.action_type == "raise"
        assert result.amount == 500

    def test_parse_raise_to(self, legal_actions_all):
        """Test parsing RAISE TO syntax."""
        result = ActionParser.parse("RAISE TO 750", legal_actions_all)

        assert result.success
        assert result.action_type == "raise"
        assert result.amount == 750

    def test_parse_raise_clamped_to_max(self, legal_actions_all):
        """Test that raise amount is clamped to max."""
        result = ActionParser.parse("RAISE 5000", legal_actions_all)

        assert result.success
        assert result.action_type == "raise"
        assert result.amount == 1000  # Max raise

    def test_parse_all_in(self, legal_actions_all):
        """Test parsing ALL IN."""
        result = ActionParser.parse("I'm going ALL IN!", legal_actions_all)

        assert result.success
        assert result.action_type == "raise"
        assert result.amount == 1000  # Max raise

    def test_parse_case_insensitive(self, legal_actions_all):
        """Test case insensitivity."""
        result = ActionParser.parse("fold", legal_actions_all)
        assert result.success
        assert result.action_type == "fold"

        result = ActionParser.parse("FOLD", legal_actions_all)
        assert result.success
        assert result.action_type == "fold"

    def test_parse_failure(self, legal_actions_all):
        """Test parsing failure with gibberish."""
        result = ActionParser.parse("I'm thinking about something...", legal_actions_all)

        assert not result.success
        assert result.action_type == "fold"  # Default

    def test_default_action_check_preferred(self, legal_actions_all):
        """Test that default action prefers check over fold."""
        result = ActionParser.get_default_action(legal_actions_all)

        assert not result.success
        assert result.action_type == "check"

    def test_default_action_fold_when_no_check(self, legal_actions_no_check):
        """Test that default action is fold when check not available."""
        result = ActionParser.get_default_action(legal_actions_no_check)

        assert not result.success
        assert result.action_type == "fold"
