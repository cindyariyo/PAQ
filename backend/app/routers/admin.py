"""
Admin monitoring endpoint — password-protected study progress dashboard.
Access during the study at: https://yoursite.com/admin/status?key=YOUR_ADMIN_KEY

Returns an HTML page (open in browser) or JSON (append &format=json).
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db import get_db
from ..models import User, UserProfile, Session as QuizSession, Attempt, QuestionnaireResponse

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_KEY = os.environ.get("ADMIN_KEY", "changeme")


def _check_key(key: str = Query(..., description="Admin access key")):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@router.get("/status", response_class=HTMLResponse)
def study_status(key: str = Query(...), fmt: str = Query("html"), db: Session = Depends(get_db)):
    _check_key(key)

    users = db.query(User).all()
    rows = []

    for u in users:
        profile = db.query(UserProfile).filter(UserProfile.user_id == u.id).first()
        if not profile:
            continue

        completed_sessions = (
            db.query(QuizSession)
            .filter(QuizSession.user_id == u.id, QuizSession.completed == True)  # noqa
            .order_by(QuizSession.session_number)
            .all()
        )
        all_sessions = (
            db.query(QuizSession)
            .filter(QuizSession.user_id == u.id)
            .order_by(QuizSession.session_number)
            .all()
        )

        sessions_done = len(completed_sessions)
        total_xp = sum(s.xp for s in completed_sessions)
        total_answered = sum(s.questions_answered for s in completed_sessions)
        total_first_correct = sum(s.first_attempt_correct for s in completed_sessions)
        accuracy = round(100 * total_first_correct / total_answered) if total_answered else 0

        # Questionnaires submitted
        q_submitted = 0
        for s in completed_sessions:
            if db.query(QuestionnaireResponse).filter(
                    QuestionnaireResponse.session_id == s.id).first():
                q_submitted += 1

        # Last active
        last_s = all_sessions[-1] if all_sessions else None
        last_active = last_s.started_at.strftime("%d %b %H:%M") if last_s and last_s.started_at else "Never"

        # Session-by-session detail
        session_cells = []
        for n in range(1, 7):
            match = next((s for s in completed_sessions if s.session_number == n), None)
            if match:
                qr = db.query(QuestionnaireResponse).filter(
                    QuestionnaireResponse.session_id == match.id).first()
                q_icon = "Q" if qr else "q"  # uppercase = questionnaire done
                acc = round(100 * match.first_attempt_correct / match.questions_answered) if match.questions_answered else 0
                session_cells.append(
                    f'<td style="text-align:center; background:#1a3a1a; color:#6f6;">'
                    f'L{match.difficulty_level_used}<br>'
                    f'<small>{acc}% {q_icon}</small></td>'
                )
            else:
                # Check if there's an incomplete session for this number
                incomplete = next((s for s in all_sessions
                                   if s.session_number == n and not s.completed), None)
                if incomplete:
                    session_cells.append(
                        '<td style="text-align:center; background:#3a3a1a; color:#fa0;">'
                        'In<br><small>progress</small></td>'
                    )
                else:
                    session_cells.append('<td style="text-align:center; color:#555;">-</td>')

        rows.append({
            "display_name": u.display_name or u.study_code,
            "hexad_type": profile.hexad_type,
            "sessions_done": sessions_done,
            "q_submitted": q_submitted,
            "total_xp": total_xp,
            "accuracy": accuracy,
            "last_active": last_active,
            "session_cells": "".join(session_cells),
            "complete": sessions_done >= 6,
        })

    # Summary counts
    total_users = len(rows)
    fully_done = sum(1 for r in rows if r["complete"])
    in_progress = sum(1 for r in rows if 0 < r["sessions_done"] < 6)
    not_started = sum(1 for r in rows if r["sessions_done"] == 0)

    if fmt == "json":
        from fastapi.responses import JSONResponse
        return JSONResponse({
            "total_participants": total_users,
            "fully_complete": fully_done,
            "in_progress": in_progress,
            "not_started": not_started,
            "participants": [
                {k: v for k, v in r.items() if k != "session_cells"}
                for r in rows
            ]
        })

    # Build HTML
    table_rows = ""
    for r in rows:
        done_colour = "#2a4a2a" if r["complete"] else "#1e1e2e"
        table_rows += f"""
        <tr style="background:{done_colour};">
          <td><b>{r['display_name']}</b></td>
          <td>{r['hexad_type']}</td>
          <td style="text-align:center;">{r['sessions_done']} / 6</td>
          <td style="text-align:center;">{r['q_submitted']}</td>
          {r['session_cells']}
          <td style="text-align:center;">{r['accuracy']}%</td>
          <td style="text-align:center;">{r['total_xp']}</td>
          <td>{r['last_active']}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta http-equiv="refresh" content="60"/>
  <title>Study Monitor</title>
  <style>
    body {{ font-family: monospace; background:#111; color:#ccc; padding:20px; }}
    h1 {{ color:#fff; margin-bottom:4px; }}
    .summary {{ display:flex; gap:20px; margin:12px 0 20px; }}
    .tile {{ background:#1e1e2e; padding:12px 20px; border-radius:8px; text-align:center; }}
    .tile .n {{ font-size:28px; font-weight:bold; color:#7af; }}
    .tile .l {{ font-size:12px; color:#888; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; }}
    th {{ background:#222; color:#aaa; padding:8px 10px; text-align:left; border-bottom:1px solid #333; }}
    td {{ padding:7px 10px; border-bottom:1px solid #222; }}
    .legend {{ font-size:11px; color:#666; margin-top:12px; }}
  </style>
</head>
<body>
  <h1>Study Progress Monitor</h1>
  <p style="color:#666; font-size:12px;">Auto-refreshes every 60s &nbsp;|&nbsp;
     <a href="?key={key}&fmt=json" style="color:#7af;">JSON</a></p>

  <div class="summary">
    <div class="tile"><div class="n">{total_users}</div><div class="l">Participants</div></div>
    <div class="tile"><div class="n" style="color:#6f6;">{fully_done}</div><div class="l">All 6 done</div></div>
    <div class="tile"><div class="n" style="color:#fa0;">{in_progress}</div><div class="l">In progress</div></div>
    <div class="tile"><div class="n" style="color:#f66;">{not_started}</div><div class="l">Not started</div></div>
  </div>

  <table>
    <tr>
      <th>Name</th><th>Hexad</th><th>Sessions</th><th>Q'naires</th>
      <th>S1</th><th>S2</th><th>S3</th><th>S4</th><th>S5</th><th>S6</th>
      <th>Accuracy</th><th>XP</th><th>Last Active</th>
    </tr>
    {table_rows}
  </table>

  <div class="legend">
    Green cell = completed &nbsp;|&nbsp; L# = difficulty level reached &nbsp;|&nbsp;
    Q = questionnaire submitted &nbsp;|&nbsp; q = questionnaire missing
  </div>
</body>
</html>"""

    return HTMLResponse(html)
