from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class AuthIn(BaseModel):
    study_code: str


class AuthOut(BaseModel):
    user_id: int
    study_code: str
    hexad_type: str
    display_name: Optional[str] = None


class SetDisplayNameIn(BaseModel):
    user_id: int
    display_name: str


class SetDisplayNameOut(BaseModel):
    ok: bool
    display_name: str


class OnboardingSubmitIn(BaseModel):
    user_id: int
    answers: Dict[str, int]


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
    session_number: int
    difficulty_level: int
    hexad_type: str
    settings: Dict[str, Any]
    question: QuestionOut
    xp: int = 0
    streak: int = 0
    questions_answered: int = 0
    correct_count: int = 0
    session_total_questions: int = 7


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
    difficulty_message: str
    feedback_message: str
    xp: int
    streak: int
    questions_answered: int
    correct_count: int
    session_total_questions: int = 7


class FinishOut(BaseModel):
    session_id: int
    questions_answered: int
    correct_count: int
    first_attempt_correct: int
    topics_to_review: list[str] = []


class QuestionnaireIn(BaseModel):
    enjoyment: int
    frustration: int
    effort: int
    focused: int = 3
    challenge: int = 3
    recovered: int = 3
    hints_helped: int = 3
    satisfied: int = 3
    motivated: int = 3
    favourite_features: str = ""
    free_text: str = ""


class ProfileQuestionnaireOut(BaseModel):
    enjoyment: int
    frustration: int
    effort: int
    focused: int
    challenge: int
    recovered: int
    hints_helped: int
    satisfied: int
    motivated: int
    favourite_features: str
    free_text: str


class ProfileSessionOut(BaseModel):
    session_number: int
    started_at: Optional[str]
    ended_at: Optional[str]
    difficulty_level_used: int
    questions_answered: int
    correct_count: int
    first_attempt_correct: int
    xp: int
    used_hint_this_session: bool
    questionnaire: Optional[ProfileQuestionnaireOut]


class ProfileOut(BaseModel):
    study_code: str
    display_name: Optional[str] = None
    hexad_type: str
    total_sessions: int
    total_xp: int
    overall_accuracy: int  # percentage 0-100
    sessions: List[ProfileSessionOut]


class LeaderboardEntry(BaseModel):
    rank: int
    display_name: str
    total_xp: int
    overall_accuracy: int
    sessions_completed: int
    is_active: bool = False


class SessionRankEntry(BaseModel):
    rank: int
    display_name: str
    xp: int
    accuracy: int
    correct_count: int
    questions_answered: int
    is_active: bool = False


class SessionLeaderboard(BaseModel):
    session_number: int
    entries: List[SessionRankEntry]


class LeaderboardOut(BaseModel):
    total_users: int
    total_class_xp: int = 0
    overall: List[LeaderboardEntry]
    sessions: List[SessionLeaderboard]