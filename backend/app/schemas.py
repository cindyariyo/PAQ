from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class StartSessionOut(BaseModel):
    session_id: int
    difficulty_level: int
    hexad_type: str
    settings: dict
    question: Any  # your QuestionOut

    # add these:
    xp: int = 0
    streak: int = 0
    questions_answered: int = 0
    correct_count: int = 0
    session_total_questions: int = 7
    
    
class AuthIn(BaseModel):
    study_code: str = Field(min_length=3, max_length=32)


class AuthOut(BaseModel):
    user_id: int
    study_code: str
    hexad_type: str


class OnboardingSubmitIn(BaseModel):
    user_id: int
    answers: Dict[str, int]  # question_id -> score (1-5)


class OnboardingOut(BaseModel):
    user_id: int
    hexad_type: str
    settings: Dict[str, Any]


class StartSessionIn(BaseModel):
    user_id: int


class QuestionOut(BaseModel):
    id: int
    topic: str
    difficulty: int
    prompt: str
    options: List[str]


class StartSessionOut(BaseModel):
    session_id: int
    difficulty_level: int
    hexad_type: str
    settings: Dict[str, Any]
    question: QuestionOut


class HintOut(BaseModel):
    hint_level: int
    hint_text: str


class AnswerIn(BaseModel):
    user_id: int
    question_id: int
    answer: str
    time_spent_seconds: int
    retry_count: int = 0
    hint_level_shown: int = 0



class AnswerOut(BaseModel):
    correct: bool
    explanation: str
    next_question: Optional[Any] = None
    updated_difficulty_level: int

    # add these:
    difficulty_message: str
    feedback_message: str
    xp: int
    streak: int
    questions_answered: int
    correct_count: int
    session_total_questions: int = 7


class FinishOut(BaseModel):
    session_id: int
    total_questions: int
    correct_count: int


class QuestionnaireIn(BaseModel):
    enjoyment: int
    frustration: int
    effort: int
    free_text: str = ""
