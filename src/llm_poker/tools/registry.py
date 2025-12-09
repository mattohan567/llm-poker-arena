"""Tool registry with OpenAI-format tool definitions for LLM agents."""

# Tool definitions in OpenAI function calling format
POKER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "pot_odds_calculator",
            "description": "Calculate pot odds to determine if a call is mathematically profitable. Use this when facing a bet to understand what equity you need to call profitably. Returns pot odds as a percentage and ratio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pot_size": {
                        "type": "integer",
                        "description": "Current pot size in chips (before your call)"
                    },
                    "bet_to_call": {
                        "type": "integer",
                        "description": "Amount you need to call in chips"
                    }
                },
                "required": ["pot_size", "bet_to_call"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "equity_calculator",
            "description": "Calculate your probability of winning the hand using Monte Carlo simulation. Use this to estimate your chances of winning against opponents' random hands. Compare the result with pot odds to make optimal decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hole_cards": {
                        "type": "string",
                        "description": "Your hole cards in format 'RankSuit RankSuit', e.g., 'AsKh' for Ace of spades and King of hearts. Use s=spades, h=hearts, d=diamonds, c=clubs."
                    },
                    "community_cards": {
                        "type": "string",
                        "description": "Community cards on board in same format, e.g., 'Jc7d2s' for Jack of clubs, 7 of diamonds, 2 of spades. Use empty string '' for preflop."
                    },
                    "num_opponents": {
                        "type": "integer",
                        "description": "Number of active opponents still in the hand (1-5)"
                    }
                },
                "required": ["hole_cards", "community_cards", "num_opponents"]
            }
        }
    }
]


def get_tool_definitions() -> list[dict]:
    """Return the list of tool definitions for LLM agents."""
    return POKER_TOOLS


def get_tool_names() -> list[str]:
    """Return list of available tool names."""
    return [tool["function"]["name"] for tool in POKER_TOOLS]
