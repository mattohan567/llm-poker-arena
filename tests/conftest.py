"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_hole_cards():
    """Sample hole cards for testing."""
    return "AsKh"


@pytest.fixture
def sample_board():
    """Sample board for testing."""
    return "Jc7d2s"


@pytest.fixture
def sample_models():
    """Sample models for testing."""
    return ["openai/gpt-4o", "anthropic/claude-sonnet-4-20250514"]
