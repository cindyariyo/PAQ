def hint_level_from_rules(time_spent: int, retry_count: int, current_hint_level: int) -> int:
    """
    Hint 1 if time > 45s OR retry_count >= 2
    Hint 2 if time > 75s OR retry_count >= 3
    """
    level = current_hint_level
    if time_spent > 75 or retry_count >= 3:
        level = max(level, 2)
    elif time_spent > 45 or retry_count >= 2:
        level = max(level, 1)
    return level


def update_difficulty(
    session,
    *,
    correct: bool,
    time_spent: int,
    retries: int,
    used_hint: bool,
    hexad: str,
    session_floor: int = 1,
    difficulty_level: int = 1,
):
    """
    Adapts difficulty_level_used on the session object after each answer.

    Rules:
    - Decrease if: wrong after >=1 retry OR time > 90s
      Floor: never below session_floor (which is max(1, starting_level - 1))
    - Increase if: 2 consecutive strong-correct answers (correct + no hint + <40s)
      Achiever: only needs 1 strong correct to level up
      Free Spirit: offered optional harder instead of forced increase
    - Max level: 5

    session_floor is passed in from the router so this function stays pure.
    """
    current = session.difficulty_level_used

    # ── Decrease ──
    # Time-based penalty doesn't apply at level 5 — harder questions take longer by design
    time_penalty = (time_spent > 90) and (current < 5)
    struggling = (not correct and retries >= 1) or time_penalty
    if struggling:
        session.strong_correct_streak = 0
        new_level = max(session_floor, current - 1)
        if new_level < current:
            return new_level, "Difficulty decreased. Take your time."
        return current, ""  # already at floor, no message

    # ── Strong correct ──
    # Time limit scales with difficulty: +5s at level 4
    strong_time_limit = 45 if difficulty_level == 4 else 40
    strong_correct = correct and (not used_hint) and (time_spent < strong_time_limit)
    if strong_correct:
        session.strong_correct_streak += 1
    else:
        session.strong_correct_streak = 0

    # All types: only first-attempt answers count toward level-up streak
    if retries > 0:
        session.strong_correct_streak = 0
        return current, ""
    required = 3  # 3 consecutive strong-correct first-try answers to level up

    if session.strong_correct_streak >= required:
        session.strong_correct_streak = 0

        new_level = min(5, current + 1)
        if new_level > current:
            msg = ("Optional harder challenge — take it if you're ready!"
                   if hexad in ("Free Spirit", "Disruptor") else "Difficulty increased. Great work!")
            return new_level, msg
        return current, "You're at the top level. Excellent!"

    return current, ""