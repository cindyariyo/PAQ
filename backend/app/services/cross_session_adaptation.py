"""
Cross-session adaptation: uses last session's behavioural data + questionnaire
to tune rewards and messaging for the upcoming session.

Returns a settings dict that is merged into profile.settings_json and also
sent to the frontend in StartSessionOut.settings.
"""


def adapt_cross_session(
    last_session,               # QuizSession ORM object  (or None for first session)
    last_questionnaire,         # QuestionnaireResponse ORM object (or None)
    base_settings: dict,        # existing profile settings_json (already parsed)
    hexad_type: str,
) -> dict:
    """
    Pure function — receives ORM objects but does NOT write to the DB.
    Returns a new settings dict that the caller should persist.
    """
    settings = dict(base_settings)  # start from whatever was already saved

    # ── defaults (neutral / no adaptation) ──
    settings.setdefault("xp_multiplier",      1.0)
    settings.setdefault("effort_xp",          False)
    settings.setdefault("streak_shield",      False)
    settings.setdefault("difficulty_offset",  0)
    settings.setdefault("protect_difficulty", False)
    settings.setdefault("hint_aggressiveness","normal")   # "low" | "normal" | "high"
    settings.setdefault("tips_variant",       "default")  # "challenge" | "recovery" | "default"
    settings.setdefault("force_leaderboard",  False)
    settings.setdefault("show_xp_breakdown",  False)
    settings.setdefault("session_start_msg",  "")
    settings.setdefault("streak_shield_active", False)    # runtime flag, reset each session

    # Nothing to adapt if this is the first session
    if last_session is None or last_questionnaire is None:
        return settings

    # ── pull signals ──
    q  = last_questionnaire
    accuracy = (
        last_session.first_attempt_correct / last_session.questions_answered
        if last_session.questions_answered > 0 else 0.0
    )
    fav = (q.favourite_features or "").lower()

    # ── reset dynamic fields so we re-derive them fresh each session ──
    settings["xp_multiplier"]       = 1.0
    settings["effort_xp"]           = False
    settings["streak_shield"]       = False
    settings["difficulty_offset"]   = 0
    settings["protect_difficulty"]  = False
    settings["hint_aggressiveness"] = "normal"
    settings["tips_variant"]        = "default"
    settings["force_leaderboard"]   = False
    settings["show_xp_breakdown"]   = False
    settings["session_start_msg"]   = ""
    settings["streak_shield_active"]= False

    # ── XP multiplier: reward effort when frustrated ──
    if q.frustration >= 4:
        settings["xp_multiplier"] = 1.3
        settings["session_start_msg"] = (
            "Last session felt tough, you've got a 1.3x XP boost this time. Keep going!"
        )

    # ── Effort XP: reward trying hard even with low accuracy ──
    if q.effort >= 4 and accuracy < 0.5:
        settings["effort_xp"] = True   # answer endpoint grants +5 bonus XP for any attempt

    # ── Streak shield: protect streak for low-motivation users ──
    if q.motivated <= 2:
        settings["streak_shield"] = True
        if not settings["session_start_msg"]:
            settings["session_start_msg"] = (
                "You have a streak shield this session — one wrong answer won't break your streak!"
            )

    # ── Difficulty offset: too hard last time ──
    if q.frustration >= 4 and q.challenge >= 4:
        settings["difficulty_offset"] = -1

    # ── Difficulty offset: too easy last time ──
    elif q.challenge <= 2 and q.satisfied >= 4:
        settings["difficulty_offset"] = 1

    # ── Protect difficulty: avoid drops for fragile motivation ──
    if q.motivated <= 2 or q.frustration >= 4:
        settings["protect_difficulty"] = True

    # ── Hint aggressiveness ──
    if q.recovered <= 2 or q.hints_helped >= 4:
        settings["hint_aggressiveness"] = "high"   # show hints earlier (lower time/retry thresholds)
    elif q.hints_helped <= 2 and q.recovered >= 4:
        settings["hint_aggressiveness"] = "low"    # show hints later

    # ── Tips variant ──
    if q.challenge >= 4 and accuracy < 0.5:
        settings["tips_variant"] = "recovery"      # softer, encouragement-focused tips
    elif q.effort >= 4 and q.challenge <= 2:
        settings["tips_variant"] = "challenge"     # push harder, stretch tips
    else:
        settings["tips_variant"] = "default"

    # ── Feature-driven flags ──
    if "leaderboard" in fav:
        settings["force_leaderboard"] = True
    if "xp & streaks" in fav:
        settings["show_xp_breakdown"] = True

    return settings
