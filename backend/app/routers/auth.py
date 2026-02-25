from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, UserProfile
from ..schemas import AuthIn, AuthOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthOut)
def login(payload: AuthIn, db: Session = Depends(get_db)):
    code = payload.study_code.strip()

    user = db.query(User).filter(User.study_code == code).first()
    if not user:
        user = User(study_code=code)
        db.add(user)
        db.commit()
        db.refresh(user)

        profile = UserProfile(user_id=user.id, hexad_type="Unknown")
        db.add(profile)
        db.commit()

    profile = user.profile
    return AuthOut(
        user_id=user.id,
        study_code=user.study_code,
        hexad_type=profile.hexad_type if profile else "Unknown",
    )
