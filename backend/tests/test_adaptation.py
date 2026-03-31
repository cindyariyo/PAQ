"""
Unit tests for app/services/adaptation.py
Pure function tests — no DB required.
"""
import pytest
from unittest.mock import MagicMock
from app.services.adaptation import update_difficulty, hint_level_from_rules


def make_session(level=2, strong_streak=0, floor=1):
    """Create a mock session object with the fields update_difficulty uses."""
    s = MagicMock()
    s.difficulty_level_used = level
    s.strong_correct_streak = strong_streak
    s.starting_difficulty = level
    return s


# ── hint_level_from_rules ────────────────────────────────────────────────

class TestHintLevelFromRules:
    def test_no_hint_below_thresholds(self):
        assert hint_level_from_rules(30, 0, 0) == 0

    def test_hint1_on_time_over_45s(self):
        assert hint_level_from_rules(50, 0, 0) == 1

    def test_hint1_on_retry_count_2(self):
        assert hint_level_from_rules(10, 2, 0) == 1

    def test_hint2_on_time_over_75s(self):
        assert hint_level_from_rules(80, 0, 0) == 2

    def test_hint2_on_retry_count_3(self):
        assert hint_level_from_rules(10, 3, 0) == 2

    def test_never_downgrade_existing_hint(self):
        # Already at level 2 — should not drop back to 1
        assert hint_level_from_rules(10, 0, 2) == 2

    def test_hint1_upgrades_to_hint2_on_threshold(self):
        assert hint_level_from_rules(80, 0, 1) == 2


# ── update_difficulty — decrease ────────────────────────────────────────

class TestUpdateDifficultyDecrease:
    def test_wrong_with_retry_decreases_level(self):
        s = make_session(level=3, floor=1)
        new_level, msg = update_difficulty(
            s, correct=False, time_spent=10, retries=1,
            used_hint=False, hexad="Achiever", session_floor=1, difficulty_level=3
        )
        assert new_level == 2
        assert "Difficulty decreased" in msg

    def test_level_never_drops_below_session_floor(self):
        s = make_session(level=2)
        new_level, _ = update_difficulty(
            s, correct=False, time_spent=10, retries=1,
            used_hint=False, hexad="Achiever", session_floor=2, difficulty_level=2
        )
        assert new_level == 2  # already at floor

    def test_time_over_90s_decreases_level(self):
        s = make_session(level=3)
        new_level, msg = update_difficulty(
            s, correct=True, time_spent=95, retries=0,
            used_hint=False, hexad="Achiever", session_floor=1, difficulty_level=3
        )
        assert new_level == 2

    def test_time_penalty_not_applied_at_level_5(self):
        # Level 5 questions are long by design — time penalty exempt
        s = make_session(level=5)
        new_level, _ = update_difficulty(
            s, correct=True, time_spent=95, retries=0,
            used_hint=False, hexad="Achiever", session_floor=1, difficulty_level=5
        )
        assert new_level == 5  # no decrease

    def test_decrease_resets_strong_streak(self):
        s = make_session(level=3, strong_streak=2)
        update_difficulty(
            s, correct=False, time_spent=10, retries=1,
            used_hint=False, hexad="Achiever", session_floor=1, difficulty_level=3
        )
        assert s.strong_correct_streak == 0


# ── update_difficulty — increase ────────────────────────────────────────

class TestUpdateDifficultyIncrease:
    def _three_strong_corrects(self, hexad="Achiever", level=2):
        s = make_session(level=level, strong_streak=0)
        for _ in range(3):
            new_level, msg = update_difficulty(
                s, correct=True, time_spent=10, retries=0,
                used_hint=False, hexad=hexad, session_floor=1,
                difficulty_level=s.difficulty_level_used
            )
        return new_level, msg, s

    def test_three_strong_corrects_increases_level(self):
        new_level, msg, _ = self._three_strong_corrects()
        assert new_level == 3
        assert "increased" in msg.lower() or "challenge" in msg.lower()

    def test_streak_resets_after_level_up(self):
        _, _, s = self._three_strong_corrects()
        assert s.strong_correct_streak == 0

    def test_level_capped_at_5(self):
        s = make_session(level=5, strong_streak=2)
        new_level, msg = update_difficulty(
            s, correct=True, time_spent=10, retries=0,
            used_hint=False, hexad="Achiever", session_floor=1, difficulty_level=5
        )
        assert new_level == 5
        assert "top level" in msg.lower()

    def test_retry_resets_streak_no_increase(self):
        s = make_session(level=2, strong_streak=2)
        new_level, msg = update_difficulty(
            s, correct=True, time_spent=10, retries=1,
            used_hint=False, hexad="Achiever", session_floor=1, difficulty_level=2
        )
        assert new_level == 2
        assert s.strong_correct_streak == 0

    def test_hint_used_prevents_strong_correct(self):
        s = make_session(level=2, strong_streak=0)
        for _ in range(3):
            update_difficulty(
                s, correct=True, time_spent=10, retries=0,
                used_hint=True, hexad="Achiever", session_floor=1,
                difficulty_level=s.difficulty_level_used
            )
        assert s.difficulty_level_used == 2  # hint used — no level up


# ── strong_time_limit thresholds ────────────────────────────────────────

class TestStrongTimeLimit:
    def _check_strong_limit(self, difficulty_level, time_just_over):
        """Answering just over the limit should NOT be strong-correct."""
        s = make_session(level=difficulty_level, strong_streak=2)
        new_level, _ = update_difficulty(
            s, correct=True, time_spent=time_just_over, retries=0,
            used_hint=False, hexad="Achiever", session_floor=1,
            difficulty_level=difficulty_level
        )
        # streak should NOT have reached 3, so level stays
        assert s.difficulty_level_used == difficulty_level

    def test_level1_limit_is_40s(self):
        self._check_strong_limit(1, 41)

    def test_level2_limit_is_40s(self):
        self._check_strong_limit(2, 41)

    def test_level3_limit_is_40s(self):
        self._check_strong_limit(3, 41)

    def test_level4_limit_is_45s(self):
        self._check_strong_limit(4, 46)

    def test_level5_limit_is_50s(self):
        self._check_strong_limit(5, 51)

    def test_level4_under_45s_counts_as_strong(self):
        s = make_session(level=4, strong_streak=0)
        new_level = 4
        for _ in range(3):
            new_level, _ = update_difficulty(
                s, correct=True, time_spent=44, retries=0,
                used_hint=False, hexad="Achiever", session_floor=1,
                difficulty_level=4
            )
        assert new_level == 5  # levelled up (return value; router sets session.difficulty_level_used)
