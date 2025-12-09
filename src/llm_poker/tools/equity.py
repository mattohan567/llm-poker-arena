"""Equity calculator tool using Monte Carlo simulation."""

from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pokerkit import (
    calculate_equities,
    parse_range,
    Card,
    Deck,
    StandardHighHand,
)


def get_random_range() -> frozenset:
    """Get a range representing all possible 2-card hands (random hand)."""
    cards = list(Deck.STANDARD)
    all_combos = [frozenset(combo) for combo in combinations(cards, 2)]
    return frozenset(all_combos)


def normalize_card_string(cards: str) -> str:
    """
    Normalize card string to standard format (e.g., AsKh).
    Handles common LLM formatting mistakes.
    """
    if not cards:
        return ""

    # Remove spaces and common separators
    cards = cards.replace(" ", "").replace(",", "").replace("-", "")

    # Handle formats like "AK suited" or "AKs" -> need to expand
    cards_lower = cards.lower()
    if "suited" in cards_lower:
        cards = cards_lower.replace("suited", "s")
    if "offsuit" in cards_lower:
        cards = cards_lower.replace("offsuit", "o")

    # If we have just ranks without suits (e.g., "AK"), use spades/hearts as default
    if len(cards) == 2 and cards[0].upper() in "AKQJT98765432" and cards[1].upper() in "AKQJT98765432":
        return cards[0].upper() + "s" + cards[1].upper() + "h"

    # If we have 3 chars like "AKs" or "AKo" (range notation), expand to specific cards
    if len(cards) == 3 and cards[2].lower() in "so":
        r1, r2, suit_type = cards[0].upper(), cards[1].upper(), cards[2].lower()
        if suit_type == "s":
            return r1 + "s" + r2 + "s"  # Suited = same suit
        else:
            return r1 + "s" + r2 + "h"  # Offsuit = different suits

    # Standard 4-char format - just ensure proper case
    if len(cards) == 4:
        return cards[0].upper() + cards[1].lower() + cards[2].upper() + cards[3].lower()

    return cards


def calculate_equity(
    hole_cards: str,
    community_cards: str,
    num_opponents: int,
    sample_count: int = 1000,
) -> dict:
    """
    Calculate hand equity using Monte Carlo simulation.

    Args:
        hole_cards: Your hole cards, e.g., "AsKh" for Ace of spades and King of hearts
        community_cards: Community cards on board, e.g., "Jc7d2s". Empty string for preflop.
        num_opponents: Number of active opponents still in the hand (1-5)
        sample_count: Number of Monte Carlo simulations (default 1000)

    Returns:
        dict with:
        - equity_percentage: float (e.g., 65.5 means you have 65.5% equity)
        - win_probability: float (same as equity_percentage)
        - opponents: int
        - sample_size: int
        - confidence: str ("high" if sample_count >= 1000)
        - recommendation: str
    """
    # Validate inputs
    num_opponents = max(1, min(num_opponents, 5))
    sample_count = max(100, min(sample_count, 5000))

    # Normalize card strings to handle LLM formatting mistakes
    hole_cards = normalize_card_string(hole_cards)
    community_cards = normalize_card_string(community_cards) if community_cards else ""

    try:
        # Parse hole cards
        hero_range = parse_range(hole_cards)

        # Parse board if we have community cards
        if community_cards and community_cards.strip():
            board = tuple(Card.parse(community_cards))
        else:
            board = ()

        # Create opponent ranges (random hands)
        random_range = get_random_range()
        ranges = [hero_range] + [random_range] * num_opponents

        # Calculate how many cards still need to be dealt
        cards_on_board = len(board)
        cards_to_deal = 5 - cards_on_board  # Need 5 total community cards

        # Run Monte Carlo simulation
        with ProcessPoolExecutor() as executor:
            equities = calculate_equities(
                ranges,
                board,
                cards_to_deal,
                5,  # Total board cards
                Deck.STANDARD,
                (StandardHighHand,),
                sample_count=sample_count,
                executor=executor,
            )

        hero_equity = equities[0] * 100

        # Build recommendation based on equity
        if hero_equity >= 70:
            recommendation = f"Very strong hand! With {hero_equity:.1f}% equity, you should bet for value and consider raising."
        elif hero_equity >= 50:
            recommendation = f"Solid equity at {hero_equity:.1f}%. You're ahead of random hands. Consider betting or calling."
        elif hero_equity >= 35:
            recommendation = f"Marginal equity at {hero_equity:.1f}%. Proceed with caution, consider pot odds before calling."
        elif hero_equity >= 20:
            recommendation = f"Weak equity at {hero_equity:.1f}%. Only continue with good pot odds or as a semi-bluff."
        else:
            recommendation = f"Very weak equity at {hero_equity:.1f}%. Consider folding unless you have great pot odds."

        return {
            "equity_percentage": round(hero_equity, 1),
            "win_probability": round(hero_equity, 1),
            "opponents": num_opponents,
            "sample_size": sample_count,
            "confidence": "high" if sample_count >= 1000 else "medium",
            "recommendation": recommendation,
        }

    except Exception as e:
        # Return a fallback if calculation fails
        return {
            "equity_percentage": 50.0,
            "win_probability": 50.0,
            "opponents": num_opponents,
            "sample_size": 0,
            "confidence": "error",
            "recommendation": f"Could not calculate equity: {str(e)}. Assuming 50% as baseline.",
            "error": str(e),
        }


def get_preflop_equity_estimate(hole_cards: str, num_opponents: int) -> dict:
    """
    Quick preflop equity estimate based on hand strength categories.
    Faster than Monte Carlo for preflop decisions.

    Args:
        hole_cards: Your hole cards, e.g., "AsKh"
        num_opponents: Number of opponents

    Returns:
        dict with equity estimate
    """
    # Parse cards
    cards = hole_cards.upper().replace(" ", "")
    if len(cards) != 4:
        return calculate_equity(hole_cards, "", num_opponents, 500)

    rank1, suit1 = cards[0], cards[1]
    rank2, suit2 = cards[2], cards[3]

    is_suited = suit1 == suit2
    is_pair = rank1 == rank2

    # Rank values
    rank_values = {"A": 14, "K": 13, "Q": 12, "J": 11, "T": 10,
                   "9": 9, "8": 8, "7": 7, "6": 6, "5": 5, "4": 4, "3": 3, "2": 2}

    r1 = rank_values.get(rank1, 0)
    r2 = rank_values.get(rank2, 0)

    # Simple equity estimates (vs random hands, heads-up baseline)
    base_equity = 50.0

    if is_pair:
        # Pairs: 55-85% equity heads up
        pair_equity = {14: 85, 13: 82, 12: 80, 11: 78, 10: 75,
                       9: 72, 8: 69, 7: 66, 6: 63, 5: 60, 4: 57, 3: 54, 2: 51}
        base_equity = pair_equity.get(r1, 65)
    else:
        # Non-pairs
        high_card = max(r1, r2)
        low_card = min(r1, r2)
        gap = high_card - low_card

        # High card contribution
        if high_card >= 14:  # Ace
            base_equity = 60
        elif high_card >= 13:  # King
            base_equity = 57
        elif high_card >= 12:  # Queen
            base_equity = 54
        else:
            base_equity = 50

        # Kicker adjustment
        if low_card >= 10:
            base_equity += 5
        elif low_card >= 7:
            base_equity += 2

        # Suited bonus
        if is_suited:
            base_equity += 3

        # Connectedness bonus
        if gap <= 3:
            base_equity += 2

    # Adjust for number of opponents (equity decreases with more opponents)
    opponent_multiplier = {1: 1.0, 2: 0.85, 3: 0.75, 4: 0.67, 5: 0.60}
    multiplier = opponent_multiplier.get(num_opponents, 0.55)
    adjusted_equity = base_equity * multiplier

    if adjusted_equity >= 60:
        recommendation = "Premium hand - raise for value."
    elif adjusted_equity >= 45:
        recommendation = "Solid hand - consider raising or calling."
    elif adjusted_equity >= 30:
        recommendation = "Speculative hand - play carefully based on position and pot odds."
    else:
        recommendation = "Weak hand - consider folding or only playing in late position."

    return {
        "equity_percentage": round(adjusted_equity, 1),
        "win_probability": round(adjusted_equity, 1),
        "opponents": num_opponents,
        "sample_size": 0,
        "confidence": "estimate",
        "recommendation": recommendation,
    }
