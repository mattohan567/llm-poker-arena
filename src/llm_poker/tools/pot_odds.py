"""Pot odds calculator tool for poker agents."""


def calculate_pot_odds(pot_size: int, bet_to_call: int) -> dict:
    """
    Calculate pot odds to determine if a call is mathematically profitable.

    Args:
        pot_size: Current pot size in chips
        bet_to_call: Amount needed to call in chips

    Returns:
        dict with:
        - pot_odds_percentage: float (e.g., 25.0 means you need 25% equity to call)
        - pot_odds_ratio: str (e.g., "3.0:1")
        - break_even_equity: float
        - recommendation: str explaining the calculation
    """
    if bet_to_call <= 0:
        return {
            "pot_odds_percentage": 0.0,
            "pot_odds_ratio": "0:1",
            "break_even_equity": 0.0,
            "recommendation": "No bet to call - check is free, any hand has positive expected value."
        }

    # Total pot after you call
    total_pot_after_call = pot_size + bet_to_call

    # Pot odds as percentage: bet_to_call / total_pot_after_call
    # This is the equity you need to break even
    pot_odds_pct = (bet_to_call / total_pot_after_call) * 100

    # Pot odds ratio: pot_size : bet_to_call
    # e.g., if pot is 300 and bet is 100, ratio is 3:1
    ratio = pot_size / bet_to_call if bet_to_call > 0 else float("inf")

    # Build recommendation
    if pot_odds_pct < 20:
        recommendation = f"Excellent pot odds! You only need {pot_odds_pct:.1f}% equity to call profitably. Consider calling with a wide range of draws and made hands."
    elif pot_odds_pct < 33:
        recommendation = f"Good pot odds. You need {pot_odds_pct:.1f}% equity to call. Most draws and medium-strength hands can call."
    elif pot_odds_pct < 40:
        recommendation = f"Marginal pot odds. You need {pot_odds_pct:.1f}% equity to call. Only call with strong draws or made hands."
    else:
        recommendation = f"Poor pot odds. You need {pot_odds_pct:.1f}% equity to call. Fold weak hands and marginal draws."

    return {
        "pot_odds_percentage": round(pot_odds_pct, 1),
        "pot_odds_ratio": f"{ratio:.1f}:1",
        "break_even_equity": round(pot_odds_pct, 1),
        "recommendation": recommendation,
    }
