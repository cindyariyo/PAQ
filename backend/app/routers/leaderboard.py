from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session as DbSession

from ..db import get_db
from ..models import User, Session as QuizSession
from ..schemas import LeaderboardOut, LeaderboardEntry, SessionRankEntry, SessionLeaderboard

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=LeaderboardOut)
def get_leaderboard(db: DbSession = Depends(get_db)):
    # Include completed sessions AND in-progress sessions with at least 1 answer
    sessions = (
        db.query(QuizSession)
        .filter(or_(QuizSession.completed == True, QuizSession.questions_answered > 0))  # noqa
        .all()
    )

    if not sessions:
        return LeaderboardOut(total_users=0, overall=[], sessions=[])

    # Pre-fetch all relevant users in one query
    user_ids = {s.user_id for s in sessions}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    # ── Overall: aggregate per user across all sessions ──
    agg: dict[int, dict] = {}
    for s in sessions:
        if s.user_id not in agg:
            agg[s.user_id] = {
                "total_xp": 0, "total_answered": 0,
                "total_correct": 0, "sessions_completed": 0,
                "is_active": False,
            }
        agg[s.user_id]["total_xp"]          += s.xp
        agg[s.user_id]["total_answered"]    += s.questions_answered
        agg[s.user_id]["total_correct"]     += s.correct_count
        if s.completed:
            agg[s.user_id]["sessions_completed"] += 1
        if not s.completed and s.questions_answered > 0:
            agg[s.user_id]["is_active"] = True

    total_users = len(agg)

    overall_raw = []
    for uid, data in agg.items():
        if uid not in users:
            continue
        acc = round((data["total_correct"] / data["total_answered"]) * 100) if data["total_answered"] else 0
        overall_raw.append({
            "study_code": users[uid].study_code,
            "total_xp": data["total_xp"],
            "overall_accuracy": acc,
            "sessions_completed": data["sessions_completed"],
            "is_active": data["is_active"],
        })

    overall_raw.sort(key=lambda e: (-e["total_xp"], -e["overall_accuracy"]))
    overall = [LeaderboardEntry(rank=i + 1, **e) for i, e in enumerate(overall_raw)]

    # ── Per-session rankings (sessions with 2+ participants) ──
    session_map: dict[int, list] = {}
    for s in sessions:
        session_map.setdefault(s.session_number, []).append(s)

    session_boards = []
    for sn in sorted(session_map.keys()):
        entries_for_sn = session_map[sn]
        if len(entries_for_sn) < 2:
            continue

        entries_raw = []
        for s in entries_for_sn:
            if s.user_id not in users:
                continue
            acc = round((s.correct_count / s.questions_answered) * 100) if s.questions_answered else 0
            entries_raw.append({
                "study_code": users[s.user_id].study_code,
                "xp": s.xp,
                "accuracy": acc,
                "correct_count": s.correct_count,
                "questions_answered": s.questions_answered,
                "is_active": not s.completed and s.questions_answered > 0,
            })

        entries_raw.sort(key=lambda e: (-e["xp"], -e["accuracy"]))
        entries = [SessionRankEntry(rank=i + 1, **e) for i, e in enumerate(entries_raw)]
        session_boards.append(SessionLeaderboard(session_number=sn, entries=entries))

    return LeaderboardOut(total_users=total_users, overall=overall, sessions=session_boards)
