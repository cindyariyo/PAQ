from typing import Dict, Tuple

HEXAD_TYPES = [
    "Achiever",
    "Player",
    "Socialiser",
    "Free Spirit",
    "Philanthropist",
    "Disruptor",
]


def score_hexad(answers: Dict[str, int]) -> Tuple[str, Dict[str, int]]:
    """
    MVP scorer:
    Expects keys like 'Achiever_1', 'Player_1', 'FreeSpirit_1', etc.
    Adds scores by matching prefix.
    """
    scores = {t: 0 for t in HEXAD_TYPES}

    for key, val in answers.items():
        k = key.lower()

        if k.startswith("achiever"):
            scores["Achiever"] += int(val)
        elif k.startswith("player"):
            scores["Player"] += int(val)
        elif k.startswith("socialiser") or k.startswith("socializer"):
            scores["Socialiser"] += int(val)
        elif k.startswith("freespirit") or k.startswith("free_spirit") or k.startswith("free spirit"):
            scores["Free Spirit"] += int(val)
        elif k.startswith("philanthropist"):
            scores["Philanthropist"] += int(val)
        elif k.startswith("disruptor"):
            scores["Disruptor"] += int(val)

    hexad_type = max(scores, key=scores.get) if any(scores.values()) else "Unknown"
    return hexad_type, scores


def initial_settings_for(hexad_type: str) -> dict:
    """
    MVP settings you can use on the frontend.
    """
    settings = {
        "show_xp": True,
        "show_progress": True,
        "show_leaderboard": False,
        "auto_hints": True,
    }

    if hexad_type == "Free Spirit":
        settings["auto_hints"] = False  # more autonomy

    if hexad_type == "Socialiser":
        settings["show_leaderboard"] = True

    return settings
