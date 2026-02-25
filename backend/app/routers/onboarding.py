import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import UserProfile
from ..schemas import OnboardingSubmitIn, OnboardingOut
from ..services.profiling import score_hexad, initial_settings_for

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/questions")
def onboarding_questions():
    # MVP short Hexad questionnaire
    return [
        {"id": "Achiever_1", "text": "I feel motivated by mastering hard tasks.", "scale": "1-5"},
        {"id": "Player_1", "text": "Rewards and points motivate me.", "scale": "1-5"},
        {"id": "Socialiser_1", "text": "I like learning with others / comparing progress.", "scale": "1-5"},
        {"id": "FreeSpirit_1", "text": "I like freedom and exploring different paths.", "scale": "1-5"},
        {"id": "Philanthropist_1", "text": "I enjoy helping others succeed.", "scale": "1-5"},
        {"id": "Disruptor_1", "text": "I like changing/improving systems.", "scale": "1-5"},
    ]


@router.post("/submit", response_model=OnboardingOut)
def submit(payload: OnboardingSubmitIn, db: Session = Depends(get_db)):
    profile = db.query(UserProfile).filter(UserProfile.user_id == payload.user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    hexad_type, scores = score_hexad(payload.answers)
    settings = initial_settings_for(hexad_type)

    profile.hexad_type = hexad_type
    profile.onboarding_answers_json = json.dumps({"answers": payload.answers, "scores": scores})
    profile.settings_json = json.dumps(settings)

    db.commit()
    return OnboardingOut(user_id=payload.user_id, hexad_type=hexad_type, settings=settings)
