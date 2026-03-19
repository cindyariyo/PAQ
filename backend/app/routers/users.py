from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, UserProfile, Session as QuizSession, Attempt, QuestionnaireResponse
from ..schemas import ProfileOut, ProfileSessionOut, ProfileQuestionnaireOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}/profile", response_model=ProfileOut)
def get_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    hexad_type = profile.hexad_type if profile else "Unknown"

    completed_sessions = (
        db.query(QuizSession)
        .filter(QuizSession.user_id == user_id, QuizSession.completed == True)  # noqa
        .order_by(QuizSession.session_number)
        .all()
    )

    total_xp = sum(s.xp for s in completed_sessions)
    total_answered = sum(s.questions_answered for s in completed_sessions)
    total_first_correct = sum(s.first_attempt_correct for s in completed_sessions)
    overall_accuracy = round((total_first_correct / total_answered) * 100) if total_answered else 0

    session_outs = []
    for s in completed_sessions:
        qr = db.query(QuestionnaireResponse).filter(
            QuestionnaireResponse.session_id == s.id
        ).first()
        questionnaire = ProfileQuestionnaireOut(
            enjoyment=qr.enjoyment,
            frustration=qr.frustration,
            effort=qr.effort,
            free_text=qr.free_text or "",
        ) if qr else None

        session_outs.append(ProfileSessionOut(
            session_number=s.session_number,
            started_at=s.started_at.strftime("%d %b %Y, %H:%M") if s.started_at else None,
            ended_at=s.ended_at.strftime("%d %b %Y, %H:%M") if s.ended_at else None,
            difficulty_level_used=s.difficulty_level_used,
            questions_answered=s.questions_answered,
            correct_count=s.correct_count,
            first_attempt_correct=s.first_attempt_correct,
            xp=s.xp,
            used_hint_this_session=s.used_hint_this_session,
            questionnaire=questionnaire,
        ))

    return ProfileOut(
        study_code=user.study_code,
        display_name=user.display_name,
        hexad_type=hexad_type,
        total_sessions=len(completed_sessions),
        total_xp=total_xp,
        overall_accuracy=overall_accuracy,
        sessions=session_outs,
    )
