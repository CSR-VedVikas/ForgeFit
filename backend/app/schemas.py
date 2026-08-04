from datetime import datetime, date
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field


# ---- Auth ----
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: str = ""


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    display_name: str = ""

    class Config:
        from_attributes = True


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    # Only returned in development so you can test without SMTP
    reset_token: Optional[str] = None
    reset_path: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=72)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)


class ChangeEmailRequest(BaseModel):
    password: str
    new_email: EmailStr


class MessageOut(BaseModel):
    message: str


# ---- Profile ----
class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    gender: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    age: Optional[int] = None
    daily_calorie_goal: Optional[int] = None
    rest_seconds: Optional[int] = None


class ProfileOut(BaseModel):
    display_name: str
    gender: str
    weight_kg: float
    height_cm: float
    age: int
    daily_calorie_goal: int
    rest_seconds: int

    class Config:
        from_attributes = True


# ---- Exercises ----
class ExerciseOut(BaseModel):
    id: str
    name: str
    category: str
    body_part: str
    equipment: str
    target: str
    muscle_group: str
    secondary_muscles: list[str]
    instructions_en: str
    instruction_steps_en: list[str]
    image: str
    gif_url: str
    attribution: str

    class Config:
        from_attributes = True


class ExerciseListItem(BaseModel):
    id: str
    name: str
    body_part: str
    equipment: str
    target: str
    image: str
    gif_url: str

    class Config:
        from_attributes = True


# ---- NLP drafts ----
class DraftSet(BaseModel):
    exercise_id: Optional[str] = None
    exercise_name: str
    weight_kg: float = 0
    reps: int = 0
    set_number: int = 1
    match_confidence: float = 0
    suggestions: list[dict[str, Any]] = []
    needs_confirm: bool = False


class DraftFood(BaseModel):
    food_name: str
    calories: float
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    quantity: float | None = None
    unit: str | None = None
    confidence: float = 1.0


class DraftCardio(BaseModel):
    name: str
    duration_min: float | None = None
    calories: float = 0
    confidence: float = 1.0


class ParseRequest(BaseModel):
    text: str
    meal_type: str = "snack"


class ParseResponse(BaseModel):
    intent: str
    confidence: float
    sets: list[DraftSet] = []
    foods: list[DraftFood] = []
    cardio: list[DraftCardio] = []
    calories_burned: float = 0
    warnings: list[str] = []
    raw_query: str = ""


# ---- Workouts ----
class SetCreate(BaseModel):
    exercise_id: str
    weight_kg: float = 0
    reps: int
    set_number: int = 1


class WorkoutCreate(BaseModel):
    notes: str = ""
    source_query: str = ""
    calories_burned: float = 0
    sets: list[SetCreate]
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class SetOut(BaseModel):
    id: int
    exercise_id: str
    exercise_name: str = ""
    weight_kg: float
    reps: int
    set_number: int
    volume: float
    is_pr: bool
    pr_types: list[str] = []
    gif_url: str = ""
    image: str = ""

    class Config:
        from_attributes = True


class WorkoutOut(BaseModel):
    id: int
    started_at: datetime
    ended_at: Optional[datetime]
    notes: str
    total_volume: float
    calories_burned: float
    source_query: str
    sets: list[SetOut] = []
    new_achievements: list[dict] = []

    class Config:
        from_attributes = True


class LastSessionSet(BaseModel):
    weight_kg: float
    reps: int
    set_number: int
    volume: float
    logged_at: datetime


# ---- Nutrition ----
class FoodLogCreate(BaseModel):
    query_text: str = ""
    food_name: str
    calories: float
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    meal_type: str = "snack"
    source_confidence: float = 1.0


class FoodLogOut(BaseModel):
    id: int
    logged_at: datetime
    query_text: str
    food_name: str
    calories: float
    protein: float
    carbs: float
    fat: float
    meal_type: str
    source_confidence: float

    class Config:
        from_attributes = True


class DailyNutrition(BaseModel):
    date: date
    calories_in: float
    protein: float
    carbs: float
    fat: float
    calories_burned: float
    calorie_goal: int
    foods: list[FoodLogOut] = []


# ---- Stats ----
class AchievementOut(BaseModel):
    id: int
    type: str
    icon_key: str
    title: str
    earned_at: datetime
    metadata_json: dict = {}

    class Config:
        from_attributes = True


class ChallengeOut(BaseModel):
    week_start: date
    target_volume: float
    current_volume: float
    progress_pct: float


class HeatmapItem(BaseModel):
    body_part: str
    set_count: int
    volume: float


class DashboardOut(BaseModel):
    calories_in: float
    calories_burned: float
    calorie_goal: int
    volume_today: float
    streak_days: int
    recent_prs: list[dict]
    challenge: Optional[ChallengeOut]
    recent_achievements: list[AchievementOut]


class DailyLinkOut(BaseModel):
    date: date
    calories_in: float
    calories_burned: float
    net_calories: float
    calorie_goal: int
    volume_kg: float
    workout_minutes: float
    workout_count: int
    foods: list[FoodLogOut] = []
    workouts: list[dict] = []
    summary: str = ""


# ---- Routines (max 3 per user) ----
class RoutineExerciseIn(BaseModel):
    exercise_id: str
    default_sets: int = 3


class RoutineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    exercises: list[RoutineExerciseIn] = []


class RoutineUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    exercises: Optional[list[RoutineExerciseIn]] = None


class RoutineExerciseOut(BaseModel):
    id: int
    exercise_id: str
    exercise_name: str = ""
    body_part: str = ""
    equipment: str = ""
    image: str = ""
    gif_url: str = ""
    sort_order: int
    default_sets: int

    class Config:
        from_attributes = True


class RoutineOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    exercises: list[RoutineExerciseOut] = []

    class Config:
        from_attributes = True


class ActivityDay(BaseModel):
    date: str
    duration_min: float = 0
    volume: float = 0
    reps: int = 0


class ActivityOut(BaseModel):
    week_hours: float
    workout_count: int
    days: list[ActivityDay]
