"""
Unit tests for app/services/cross_session_adaptation.py
Pure function tests — no DB required.
"""
import pytest
from unittest.mock import MagicMock
from app.services.cross_session_adaptation import adapt_cross_session


def make_session(questions_answered=10, first_attempt_correct=5):
    s = MagicMock()
    s.questions_answered = questions_answered
    s.first_attempt_correct = first_attempt_correct
    return s


def make_questionnaire(enjoyment=3, frustration=2, effort=3, focused=3,
                       challenge=3, recovered=3, hints_helped=3,
                       satisfied=3, motivated=3, favourite_features="",
                       free_text=""):
    q = MagicMock()
    q.enjoyment = enjoyment
    q.frustration = frustration
    q.effort = effort
    q.focused = focused
    q.challenge = challenge
    q.recovered = recovered
    q.hints_helped = hints_helped
    q.satisfied = satisfied
    q.motivated = motivated
    q.favourite_features = favourite_features
    q.free_text = free_text
    return q


class TestFirstSession:
    def test_no_last_session_returns_defaults(self):
        result = adapt_cross_session(None, None, {}, "Achiever")
        assert result["xp_multiplier"] == 1.0
        assert result["effort_xp"] is False
        assert result["streak_shield"] is False
        assert result["difficulty_offset"] == 0

    def test_no_questionnaire_returns_defaults(self):
        s = make_session()
        result = adapt_cross_session(s, None, {}, "Achiever")
        assert result["xp_multiplier"] == 1.0


class TestXpMultiplier:
    def test_frustration_4_gives_1_3x_multiplier(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(frustration=4), {}, "Achiever"
        )
        assert result["xp_multiplier"] == 1.3

    def test_frustration_5_gives_1_3x_multiplier(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(frustration=5), {}, "Achiever"
        )
        assert result["xp_multiplier"] == 1.3

    def test_frustration_3_no_multiplier(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(frustration=3), {}, "Achiever"
        )
        assert result["xp_multiplier"] == 1.0

    def test_frustration_high_sets_start_message(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(frustration=4), {}, "Achiever"
        )
        assert result["session_start_msg"] != ""


class TestEffortXp:
    def test_high_effort_low_accuracy_enables_effort_xp(self):
        # accuracy = 3/10 = 0.3 < 0.5
        result = adapt_cross_session(
            make_session(10, 3), make_questionnaire(effort=4), {}, "Achiever"
        )
        assert result["effort_xp"] is True

    def test_high_effort_high_accuracy_no_effort_xp(self):
        # accuracy = 8/10 = 0.8 >= 0.5
        result = adapt_cross_session(
            make_session(10, 8), make_questionnaire(effort=4), {}, "Achiever"
        )
        assert result["effort_xp"] is False

    def test_low_effort_no_effort_xp(self):
        result = adapt_cross_session(
            make_session(10, 3), make_questionnaire(effort=2), {}, "Achiever"
        )
        assert result["effort_xp"] is False


class TestStreakShield:
    def test_low_motivation_enables_streak_shield(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(motivated=2), {}, "Achiever"
        )
        assert result["streak_shield"] is True

    def test_motivated_1_enables_streak_shield(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(motivated=1), {}, "Achiever"
        )
        assert result["streak_shield"] is True

    def test_motivated_3_no_shield(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(motivated=3), {}, "Achiever"
        )
        assert result["streak_shield"] is False


class TestDifficultyOffset:
    def test_frustrated_and_hard_gives_minus1_offset(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(frustration=4, challenge=4), {}, "Achiever"
        )
        assert result["difficulty_offset"] == -1

    def test_easy_and_satisfied_gives_plus1_offset(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(challenge=2, satisfied=4), {}, "Achiever"
        )
        assert result["difficulty_offset"] == 1

    def test_neutral_gives_zero_offset(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(), {}, "Achiever"
        )
        assert result["difficulty_offset"] == 0


class TestHintAggressiveness:
    def test_low_recovery_gives_high_aggressiveness(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(recovered=2), {}, "Achiever"
        )
        assert result["hint_aggressiveness"] == "high"

    def test_hints_helped_4_gives_high_aggressiveness(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(hints_helped=4), {}, "Achiever"
        )
        assert result["hint_aggressiveness"] == "high"

    def test_good_recovery_low_hint_need_gives_low_aggressiveness(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(hints_helped=2, recovered=4), {}, "Achiever"
        )
        assert result["hint_aggressiveness"] == "low"

    def test_neutral_gives_normal_aggressiveness(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(), {}, "Achiever"
        )
        assert result["hint_aggressiveness"] == "normal"


class TestFeatureFlags:
    def test_leaderboard_in_features_sets_force_leaderboard(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(favourite_features="Leaderboard"), {}, "Achiever"
        )
        assert result["force_leaderboard"] is True

    def test_xp_streaks_in_features_sets_show_xp_breakdown(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(favourite_features="XP & Streaks"), {}, "Achiever"
        )
        assert result["show_xp_breakdown"] is True

    def test_unrelated_feature_no_flags(self):
        result = adapt_cross_session(
            make_session(), make_questionnaire(favourite_features="Hints"), {}, "Achiever"
        )
        assert result["force_leaderboard"] is False
        assert result["show_xp_breakdown"] is False


class TestDynamicFieldsReset:
    def test_stale_multiplier_reset_each_session(self):
        # Simulate previous session having left xp_multiplier=1.3
        base = {"xp_multiplier": 1.3}
        # New session: frustration is low, so multiplier should reset to 1.0
        result = adapt_cross_session(
            make_session(), make_questionnaire(frustration=2), base, "Achiever"
        )
        assert result["xp_multiplier"] == 1.0

    def test_stale_streak_shield_cleared(self):
        base = {"streak_shield": True}
        result = adapt_cross_session(
            make_session(), make_questionnaire(motivated=4), base, "Achiever"
        )
        assert result["streak_shield"] is False
