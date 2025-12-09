"""System prompts and message templates for poker agents."""

DEFAULT_SYSTEM_PROMPT = """You are an expert poker player competing in a No-Limit Texas Hold'em tournament. Your goal is to maximize your chip stack through strategic play.

## Game Rules
- You receive 2 private hole cards
- 5 community cards are dealt: Flop (3), Turn (1), River (1)
- Make the best 5-card hand using any combination of your hole cards and community cards
- Hand rankings (highest to lowest):
  1. Royal Flush: A K Q J T all same suit
  2. Straight Flush: Five consecutive cards of same suit
  3. Four of a Kind: Four cards of same rank
  4. Full House: Three of a kind plus a pair
  5. Flush: Five cards of same suit
  6. Straight: Five consecutive cards
  7. Three of a Kind: Three cards of same rank
  8. Two Pair: Two different pairs
  9. One Pair: Two cards of same rank
  10. High Card: Highest card when no other hand

## Betting Rounds
- Preflop: After receiving hole cards, before community cards
- Flop: After first 3 community cards
- Turn: After 4th community card
- River: After 5th community card

## Available Tools
You have access to two analytical tools:

1. **pot_odds_calculator**: Calculate pot odds when facing a bet
   - Input: pot_size (current pot), bet_to_call (amount to call)
   - Output: The equity percentage you need to profitably call
   - Use when: Facing a bet and need to decide if calling is profitable

2. **equity_calculator**: Estimate your winning probability
   - Input: hole_cards, community_cards, num_opponents
   - Output: Your equity (win probability) against random hands
   - Use when: Need to know how strong your hand is

## Decision Making Framework
1. Evaluate your hand strength
2. Consider position (later = more information)
3. Assess pot odds vs your equity
4. Factor in opponent tendencies from betting history
5. Choose the action that maximizes expected value

## Response Format
After your analysis, clearly state your action using EXACTLY one of:
- FOLD - Give up your hand
- CHECK - Pass action (only when no bet to call)
- CALL - Match the current bet
- RAISE <amount> - Increase the bet (specify the TOTAL amount, not the raise size)

Example responses:
- "Based on my analysis, I will FOLD"
- "The pot odds are favorable, I CALL"
- "I have a strong hand, I RAISE 50000"
- "No bet to call, I CHECK"

IMPORTANT: Your response MUST contain one of these action words. Be decisive."""


def build_action_prompt(
    game_state: dict,
    player_index: int,
    betting_history: list[dict],
) -> str:
    """
    Build the user prompt with current game state for the LLM.

    Args:
        game_state: Current game state snapshot
        player_index: Index of the player making the decision
        betting_history: History of actions in this hand

    Returns:
        Formatted prompt string
    """
    # Extract player info
    player = game_state["players"][player_index]
    hole_cards = player.get("hole_cards", "Unknown")

    # Format community cards
    community = game_state.get("community_cards", "")
    if not community:
        community_display = "None (Preflop)"
    else:
        community_display = format_cards_display(community)

    # Format hole cards
    hole_display = format_cards_display(hole_cards) if hole_cards else "Unknown"

    # Build opponent info
    opponents_info = []
    for i, p in enumerate(game_state["players"]):
        if i != player_index:
            status = "Active" if p["is_active"] else "Folded"
            opponents_info.append(f"  Seat {i} ({p['model_name']}): {p['stack']:,} chips - {status}")

    # Format legal actions
    actions_info = []
    for action in game_state["legal_actions"]:
        if action["action_type"] == "fold":
            actions_info.append("FOLD")
        elif action["action_type"] == "check":
            actions_info.append("CHECK")
        elif action["action_type"] == "call":
            actions_info.append(f"CALL {action['amount']:,}")
        elif action["action_type"] == "raise":
            actions_info.append(f"RAISE (min: {action['min_raise']:,}, max: {action['max_raise']:,})")

    # Format betting history for this hand
    history_lines = []
    current_street = None
    for h in betting_history:
        if h["street"] != current_street:
            current_street = h["street"]
            history_lines.append(f"\n  [{current_street.upper()}]")
        model_short = h["model"].split("/")[-1][:15]
        if h["action"] == "raise":
            history_lines.append(f"  {model_short}: RAISE to {h['amount']:,}")
        elif h["action"] == "call":
            history_lines.append(f"  {model_short}: CALL {h['amount']:,}")
        elif h["action"] == "check":
            history_lines.append(f"  {model_short}: CHECK")
        elif h["action"] == "fold":
            history_lines.append(f"  {model_short}: FOLD")

    history_str = "".join(history_lines) if history_lines else "  No actions yet"

    prompt = f"""## Current Game State

**Street:** {game_state['street'].upper()}
**Pot:** {game_state['pot']:,} chips

**Your Hand:** {hole_display}
**Community Cards:** {community_display}

**Your Stack:** {player['stack']:,} chips
**Amount to Call:** {game_state['amount_to_call']:,} chips

**Opponents:**
{chr(10).join(opponents_info)}

**Betting History This Hand:**{history_str}

**Your Legal Actions:**
{chr(10).join(f"- {a}" for a in actions_info)}

---

Analyze the situation and decide your action. You may use the pot_odds_calculator and equity_calculator tools to help inform your decision.

What is your action?"""

    return prompt


def build_clarification_prompt() -> str:
    """Return prompt for clarifying an unclear action response."""
    return """Your previous response was unclear. Please respond with EXACTLY one of these actions:

- FOLD - Give up your hand
- CHECK - Pass (if no bet to call)
- CALL - Match the current bet
- RAISE <amount> - Raise to a specific total amount (e.g., RAISE 50000)

What is your action?"""


def format_cards_display(cards: str) -> str:
    """
    Format card string for display.
    e.g., "AsKh" -> "A♠ K♥"
    """
    if not cards:
        return ""

    suit_map = {"s": "♠", "h": "♥", "d": "♦", "c": "♣",
                "S": "♠", "H": "♥", "D": "♦", "C": "♣"}
    result = []

    i = 0
    while i < len(cards):
        if i + 1 < len(cards):
            rank = cards[i].upper()
            suit = suit_map.get(cards[i + 1], cards[i + 1])
            result.append(f"{rank}{suit}")
            i += 2
        else:
            break

    return " ".join(result)
