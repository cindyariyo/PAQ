def hint_level_from_rules(time_spent: int, retry_count: int, current_hint_level: int) -> int:
    """
    Design rules:
    - Hint 1 if time > 45s OR retry_count >= 2
    - Hint 2 if time > 75s OR retry_count >= 3
    """
    level = current_hint_level
    if time_spent > 75 or retry_count >= 3:
        level = max(level, 2)
    elif time_spent > 45 or retry_count >= 2:
        level = max(level, 1)
    return level


def update_difficulty(session, *, correct: bool, time_spent: int, retries: int, used_hint: bool, hexad: str):
    # Decrease rule (design chapter)
    if (not correct and retries >= 2) or (time_spent > 90):
        session.strong_correct_streak = 0
        return max(1, session.difficulty_level - 1), "Difficulty decreased (support mode)."

    # Strong correct definition for increase rule
    strong_correct = correct and (not used_hint) and (time_spent < 40)

    if strong_correct:
        session.strong_correct_streak += 1
    else:
        session.strong_correct_streak = 0

    # Hexad variation: Achiever increases after one strong performance sequence
    required_streak = 1 if hexad == "Achiever" else 2

    if session.strong_correct_streak >= required_streak:
        session.strong_correct_streak = 0
        # Free Spirit: offer harder rather than forcing
        if hexad == "Free Spirit":
            return session.difficulty_level, "Optional harder question available."
        return min(3, session.difficulty_level + 1), "Difficulty increased!"

    return session.difficulty_level, "Difficulty unchanged."
