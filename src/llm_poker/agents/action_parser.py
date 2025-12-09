"""Parser for extracting poker actions from LLM responses."""

import re
from dataclasses import dataclass


@dataclass
class ParsedAction:
    """Result of parsing an LLM response."""
    action_type: str  # "fold", "check", "call", "raise"
    amount: int | None  # For raise actions
    success: bool  # Whether parsing succeeded
    raw_match: str | None  # The matched text
    error: str | None = None


class ActionParser:
    """Parse LLM responses into structured poker actions."""

    # Patterns ordered by specificity (most specific first)
    PATTERNS = [
        # All-in variations
        (r"\b(ALL[\s-]?IN)\b", "allin", None),
        (r"\bgo\s+all[\s-]?in\b", "allin", None),

        # Raise with amount - various formats
        (r"\bRAISE\s+TO\s+(\d[\d,]*)\b", "raise", 1),
        (r"\bRAISE\s+(\d[\d,]*)\b", "raise", 1),
        (r"\braise\s+to\s+(\d[\d,]*)\b", "raise", 1),
        (r"\braise\s+(\d[\d,]*)\b", "raise", 1),
        (r"\bBET\s+(\d[\d,]*)\b", "raise", 1),
        (r"\bbet\s+(\d[\d,]*)\b", "raise", 1),

        # Simple actions (case insensitive via re.IGNORECASE)
        (r"\bFOLD\b", "fold", None),
        (r"\bfold\b", "fold", None),
        (r"\bCHECK\b", "check", None),
        (r"\bcheck\b", "check", None),
        (r"\bCALL\b", "call", None),
        (r"\bcall\b", "call", None),

        # Raise without amount (will use min raise)
        (r"\bRAISE\b", "raise", None),
        (r"\braise\b", "raise", None),
    ]

    @classmethod
    def parse(
        cls,
        response_text: str,
        legal_actions: list[dict],
    ) -> ParsedAction:
        """
        Parse an action from LLM response text.

        Args:
            response_text: Raw text response from LLM
            legal_actions: List of legal action dicts

        Returns:
            ParsedAction with parsed action or error
        """
        if not response_text:
            return ParsedAction(
                action_type="fold",
                amount=None,
                success=False,
                raw_match=None,
                error="Empty response"
            )

        # Build lookup for legal actions
        legal_types = {a["action_type"] for a in legal_actions}
        min_raise = None
        max_raise = None
        call_amount = None

        for action in legal_actions:
            if action["action_type"] == "raise":
                min_raise = action.get("min_raise")
                max_raise = action.get("max_raise")
            elif action["action_type"] == "call":
                call_amount = action.get("amount")

        # Try each pattern
        for pattern, action_type, amount_group in cls.PATTERNS:
            match = re.search(pattern, response_text)
            if match:
                amount = None

                # Handle all-in
                if action_type == "allin":
                    if "raise" in legal_types and max_raise:
                        return ParsedAction(
                            action_type="raise",
                            amount=max_raise,
                            success=True,
                            raw_match=match.group(0),
                        )
                    elif "call" in legal_types:
                        return ParsedAction(
                            action_type="call",
                            amount=call_amount,
                            success=True,
                            raw_match=match.group(0),
                        )
                    continue

                # Extract amount if present
                if amount_group is not None:
                    try:
                        amount_str = match.group(amount_group).replace(",", "")
                        amount = int(amount_str)
                    except (IndexError, ValueError):
                        pass

                # Validate action is legal
                if action_type == "raise":
                    if "raise" not in legal_types:
                        # Can't raise, try call instead
                        if "call" in legal_types:
                            return ParsedAction(
                                action_type="call",
                                amount=call_amount,
                                success=True,
                                raw_match=match.group(0),
                            )
                        continue

                    # Clamp raise amount to valid range
                    if amount is not None and min_raise and max_raise:
                        amount = max(min_raise, min(amount, max_raise))
                    elif min_raise:
                        amount = min_raise

                    return ParsedAction(
                        action_type="raise",
                        amount=amount,
                        success=True,
                        raw_match=match.group(0),
                    )

                elif action_type == "check":
                    if "check" not in legal_types:
                        # Can't check, might need to call
                        if "call" in legal_types:
                            return ParsedAction(
                                action_type="call",
                                amount=call_amount,
                                success=True,
                                raw_match=match.group(0),
                            )
                        continue
                    return ParsedAction(
                        action_type="check",
                        amount=None,
                        success=True,
                        raw_match=match.group(0),
                    )

                elif action_type == "call":
                    if "call" not in legal_types:
                        # Can't call, might want to check
                        if "check" in legal_types:
                            return ParsedAction(
                                action_type="check",
                                amount=None,
                                success=True,
                                raw_match=match.group(0),
                            )
                        continue
                    return ParsedAction(
                        action_type="call",
                        amount=call_amount,
                        success=True,
                        raw_match=match.group(0),
                    )

                elif action_type == "fold":
                    return ParsedAction(
                        action_type="fold",
                        amount=None,
                        success=True,
                        raw_match=match.group(0),
                    )

        # No pattern matched - return parse failure
        return ParsedAction(
            action_type="fold",
            amount=None,
            success=False,
            raw_match=None,
            error=f"Could not parse action from response: {response_text[:200]}"
        )

    @classmethod
    def get_default_action(cls, legal_actions: list[dict]) -> ParsedAction:
        """
        Get the safest default action when parsing fails.
        Prefers CHECK if legal, otherwise FOLD.

        Args:
            legal_actions: List of legal action dicts

        Returns:
            ParsedAction for check or fold
        """
        legal_types = {a["action_type"] for a in legal_actions}

        if "check" in legal_types:
            return ParsedAction(
                action_type="check",
                amount=None,
                success=False,
                raw_match=None,
                error="Using default action: CHECK"
            )

        return ParsedAction(
            action_type="fold",
            amount=None,
            success=False,
            raw_match=None,
            error="Using default action: FOLD"
        )
