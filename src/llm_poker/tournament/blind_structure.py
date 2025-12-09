"""Blind structure management for tournaments."""

from dataclasses import dataclass


@dataclass
class BlindLevel:
    """A single blind level."""
    small_blind: int
    big_blind: int
    ante: int = 0


class BlindStructure:
    """Manages blind levels for a tournament."""

    def __init__(
        self,
        initial_small_blind: int = 5_000,
        initial_big_blind: int = 10_000,
        initial_ante: int = 0,
        hands_per_level: int = 20,
        multiplier: float = 1.5,
        max_levels: int = 50,
    ):
        """
        Initialize blind structure.

        Args:
            initial_small_blind: Starting small blind
            initial_big_blind: Starting big blind
            initial_ante: Starting ante (0 for no ante)
            hands_per_level: Hands before blinds increase
            multiplier: Multiplier for blind increases
            max_levels: Maximum number of blind levels
        """
        self.initial_small_blind = initial_small_blind
        self.initial_big_blind = initial_big_blind
        self.initial_ante = initial_ante
        self.hands_per_level = hands_per_level
        self.multiplier = multiplier

        # Generate blind levels
        self.levels: list[BlindLevel] = []
        self._generate_levels(max_levels)

        # Current state
        self.current_level_index = 0
        self.hands_at_current_level = 0

    def _generate_levels(self, max_levels: int):
        """Generate all blind levels."""
        sb = self.initial_small_blind
        bb = self.initial_big_blind
        ante = self.initial_ante

        for _ in range(max_levels):
            self.levels.append(BlindLevel(
                small_blind=int(sb),
                big_blind=int(bb),
                ante=int(ante),
            ))

            sb *= self.multiplier
            bb *= self.multiplier
            # Ante starts at level 3 and is typically 10% of big blind
            if len(self.levels) >= 3 and ante == 0:
                ante = int(bb * 0.1)
            elif ante > 0:
                ante *= self.multiplier

    def get_current_level(self) -> BlindLevel:
        """Get current blind level."""
        return self.levels[self.current_level_index]

    def get_blinds(self) -> tuple[int, int]:
        """Get current (small_blind, big_blind)."""
        level = self.get_current_level()
        return (level.small_blind, level.big_blind)

    def get_ante(self) -> int:
        """Get current ante."""
        return self.get_current_level().ante

    def hand_completed(self) -> bool:
        """
        Call after each hand. Returns True if blinds increased.
        """
        self.hands_at_current_level += 1

        if self.hands_at_current_level >= self.hands_per_level:
            if self.current_level_index < len(self.levels) - 1:
                self.current_level_index += 1
                self.hands_at_current_level = 0
                return True

        return False

    def get_level_info(self) -> dict:
        """Get current level information."""
        level = self.get_current_level()
        return {
            "level": self.current_level_index + 1,
            "small_blind": level.small_blind,
            "big_blind": level.big_blind,
            "ante": level.ante,
            "hands_at_level": self.hands_at_current_level,
            "hands_until_increase": self.hands_per_level - self.hands_at_current_level,
        }

    def reset(self):
        """Reset to initial state."""
        self.current_level_index = 0
        self.hands_at_current_level = 0
