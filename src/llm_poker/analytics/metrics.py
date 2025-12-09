"""Poker metrics calculations."""

from dataclasses import dataclass
from typing import Any


@dataclass
class PlayerMetrics:
    """Calculated metrics for a player."""
    model: str
    hands_played: int

    # Win metrics
    hands_won: int
    win_rate: float  # Percentage
    showdowns_reached: int
    showdowns_won: int
    showdown_win_rate: float

    # Financial
    total_profit_loss: int
    avg_profit_per_hand: float
    roi: float  # Return on investment %
    biggest_pot_won: int

    # Behavioral
    vpip: float  # Voluntarily put in pot %
    pfr: float  # Pre-flop raise %
    aggression_factor: float  # (bets + raises) / calls
    three_bet_pct: float  # 3-bet percentage
    fold_to_3bet: float  # Fold to 3-bet %
    cbet_frequency: float  # Continuation bet %

    # Tool usage
    tool_usage_rate: float
    pot_odds_tool_usage: float
    equity_tool_usage: float
    pot_odds_compliance: float  # How often action aligns with pot odds

    # Cost metrics
    total_tokens: int
    total_cost_usd: float
    avg_tokens_per_decision: float
    avg_latency_ms: float
    parse_failure_rate: float


class MetricsCalculator:
    """Calculates poker metrics from decision data."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all tracking data."""
        self._decisions = []
        self._hands = []

    def add_decision(self, decision: dict):
        """Add a decision for analysis."""
        self._decisions.append(decision)

    def add_hand_result(self, hand_result: dict):
        """Add a hand result for analysis."""
        self._hands.append(hand_result)

    def calculate_metrics(self, model: str) -> PlayerMetrics:
        """Calculate all metrics for a specific model."""
        # Filter decisions for this model
        model_decisions = [d for d in self._decisions if d.get("model") == model]
        model_hands = [h for h in self._hands if model in [p.get("model") for p in h.get("players", [])]]

        if not model_decisions:
            return self._empty_metrics(model)

        # Basic counts
        hands_played = len(model_hands)
        total_decisions = len(model_decisions)

        # Win metrics
        hands_won = sum(1 for h in model_hands if self._player_won(h, model))
        showdowns_reached = sum(1 for h in model_hands if self._reached_showdown(h, model))
        showdowns_won = sum(1 for h in model_hands
                           if self._reached_showdown(h, model) and self._player_won(h, model))

        # Financial
        total_profit_loss = sum(self._get_player_profit(h, model) for h in model_hands)
        biggest_pot_won = max(
            (self._get_player_profit(h, model) for h in model_hands if self._player_won(h, model)),
            default=0
        )

        # Behavioral metrics
        preflop_decisions = [d for d in model_decisions if d.get("street") == "preflop"]
        vpip_count = sum(1 for d in preflop_decisions
                        if d.get("action_type") in ("call", "raise"))
        pfr_count = sum(1 for d in preflop_decisions
                       if d.get("action_type") == "raise")

        # Aggression
        bets_raises = sum(1 for d in model_decisions if d.get("action_type") == "raise")
        calls = sum(1 for d in model_decisions if d.get("action_type") == "call")
        aggression_factor = bets_raises / calls if calls > 0 else bets_raises

        # Tool usage
        tool_decisions = [d for d in model_decisions if d.get("tools_called")]
        pot_odds_uses = sum(1 for d in model_decisions
                           if self._used_tool(d, "pot_odds_calculator"))
        equity_uses = sum(1 for d in model_decisions
                        if self._used_tool(d, "equity_calculator"))

        # Cost metrics
        total_tokens = sum(d.get("total_tokens", 0) for d in model_decisions)
        total_cost = sum(d.get("cost_usd", 0) or 0 for d in model_decisions)
        latencies = [d.get("latency_ms", 0) for d in model_decisions if d.get("latency_ms")]
        parse_failures = sum(1 for d in model_decisions if not d.get("parse_success", True))

        return PlayerMetrics(
            model=model,
            hands_played=hands_played,

            # Win metrics
            hands_won=hands_won,
            win_rate=_pct(hands_won, hands_played),
            showdowns_reached=showdowns_reached,
            showdowns_won=showdowns_won,
            showdown_win_rate=_pct(showdowns_won, showdowns_reached),

            # Financial
            total_profit_loss=total_profit_loss,
            avg_profit_per_hand=total_profit_loss / hands_played if hands_played > 0 else 0,
            roi=_pct(total_profit_loss, hands_played * 100),  # Simplified ROI
            biggest_pot_won=biggest_pot_won,

            # Behavioral
            vpip=_pct(vpip_count, len(preflop_decisions)),
            pfr=_pct(pfr_count, len(preflop_decisions)),
            aggression_factor=round(aggression_factor, 2),
            three_bet_pct=0.0,  # Would need more complex tracking
            fold_to_3bet=0.0,  # Would need more complex tracking
            cbet_frequency=0.0,  # Would need more complex tracking

            # Tool usage
            tool_usage_rate=_pct(len(tool_decisions), total_decisions),
            pot_odds_tool_usage=_pct(pot_odds_uses, total_decisions),
            equity_tool_usage=_pct(equity_uses, total_decisions),
            pot_odds_compliance=0.0,  # Would need pot odds vs action analysis

            # Cost metrics
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            avg_tokens_per_decision=total_tokens / total_decisions if total_decisions > 0 else 0,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            parse_failure_rate=_pct(parse_failures, total_decisions),
        )

    def _empty_metrics(self, model: str) -> PlayerMetrics:
        """Return empty metrics for a model with no data."""
        return PlayerMetrics(
            model=model,
            hands_played=0,
            hands_won=0,
            win_rate=0.0,
            showdowns_reached=0,
            showdowns_won=0,
            showdown_win_rate=0.0,
            total_profit_loss=0,
            avg_profit_per_hand=0.0,
            roi=0.0,
            biggest_pot_won=0,
            vpip=0.0,
            pfr=0.0,
            aggression_factor=0.0,
            three_bet_pct=0.0,
            fold_to_3bet=0.0,
            cbet_frequency=0.0,
            tool_usage_rate=0.0,
            pot_odds_tool_usage=0.0,
            equity_tool_usage=0.0,
            pot_odds_compliance=0.0,
            total_tokens=0,
            total_cost_usd=0.0,
            avg_tokens_per_decision=0.0,
            avg_latency_ms=0.0,
            parse_failure_rate=0.0,
        )

    def _player_won(self, hand: dict, model: str) -> bool:
        """Check if player won the hand."""
        winners = hand.get("winners", [])
        return any(w.get("model") == model for w in winners)

    def _reached_showdown(self, hand: dict, model: str) -> bool:
        """Check if player reached showdown."""
        # Simplified: showdown if >1 player and hand went to river
        players = hand.get("player_results", [])
        active_at_end = sum(1 for p in players if p.get("ending_stack", 0) > 0 or p.get("won_hand"))
        return active_at_end > 1 and hand.get("board_cards", "")

    def _get_player_profit(self, hand: dict, model: str) -> int:
        """Get player's profit/loss from a hand."""
        for player in hand.get("player_results", []):
            if player.get("model") == model:
                return player.get("profit_loss", 0)
        return 0

    def _used_tool(self, decision: dict, tool_name: str) -> bool:
        """Check if a specific tool was used in a decision."""
        tools = decision.get("tools_called") or []
        return any(t.get("name") == tool_name for t in tools)


def _pct(numerator: float, denominator: float) -> float:
    """Calculate percentage safely."""
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)
