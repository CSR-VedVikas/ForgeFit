from typing import Any
from sqlalchemy.orm import Session
from rapidfuzz import fuzz

from ..config import get_settings
from ..models import ExerciseCatalog, Profile
from ..schemas import DraftSet, DraftFood, DraftCardio, ParseResponse
from . import openai_nlp, nutrition_api


def match_exercise(db: Session, name: str, limit: int = 3) -> list[tuple[ExerciseCatalog, float]]:
    exercises = db.query(ExerciseCatalog).all()
    if not exercises:
        return []

    query = name.lower().strip()
    scored: list[tuple[ExerciseCatalog, float]] = []
    for ex in exercises:
        n = ex.name.lower()
        # Prefer whole-phrase containment and token overlap for common short names
        # like "bench press" → "barbell bench press" over "band bench press".
        wr = fuzz.WRatio(query, n) / 100.0
        ts = fuzz.token_set_ratio(query, n) / 100.0
        pr = fuzz.partial_ratio(query, n) / 100.0
        score = max(wr, ts * 0.98, pr * 0.9)
        if query == n:
            score = 1.0
        elif n.endswith(query) or f" {query}" in f" {n}":
            score = max(score, 0.96)
        # Light boost for barbell/dumbbell when query doesn't specify equipment
        if "band " in n and "band" not in query:
            score -= 0.08
        if n.startswith("barbell ") and "barbell" not in query and "bench" in query:
            score += 0.04
        scored.append((ex, min(score, 0.99)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


def expand_sets(parsed: list[dict[str, Any]], db: Session) -> list[DraftSet]:
    settings = get_settings()
    threshold = settings.match_confidence_threshold
    drafts: list[DraftSet] = []
    for item in parsed:
        name = item.get("exercise_name") or "unknown"
        weight = float(item.get("weight_kg") or 0)
        reps = int(item.get("reps") or 0)
        count = max(1, int(item.get("sets_count") or 1))
        matches = match_exercise(db, name)
        best = matches[0] if matches else None
        conf = best[1] if best else 0.0
        suggestions = [
            {"id": m.id, "name": m.name, "score": round(s, 3), "gif_url": m.gif_url, "image": m.image}
            for m, s in matches
        ]
        for i in range(count):
            drafts.append(
                DraftSet(
                    exercise_id=best[0].id if best and conf >= threshold else None,
                    exercise_name=best[0].name if best and conf >= threshold else name,
                    weight_kg=weight,
                    reps=reps,
                    set_number=i + 1,
                    match_confidence=round(conf, 3),
                    suggestions=suggestions,
                    needs_confirm=conf < threshold,
                )
            )
    return drafts


async def parse_user_text(db: Session, text: str, profile: Profile | None) -> ParseResponse:
    text = text.strip()
    if not text:
        return ParseResponse(intent="unknown", confidence=0, warnings=["Empty input"], raw_query=text)

    classification = await openai_nlp.classify_intent(text)
    intent = classification.get("intent") or "strength"
    base_conf = float(classification.get("confidence") or 0.5)
    food_text = classification.get("food_text") or (text if intent == "food" else "")
    strength_text = classification.get("strength_text") or (text if intent in ("strength", "mixed") else "")
    cardio_text = classification.get("cardio_text") or (text if intent == "cardio" else "")

    sets: list[DraftSet] = []
    foods: list[DraftFood] = []
    cardio: list[DraftCardio] = []
    calories_burned = 0.0
    warnings: list[str] = []

    # Strength via OpenAI + catalog match
    if intent in ("strength", "mixed") or strength_text:
        try:
            parsed = await openai_nlp.parse_strength_sets(strength_text or text)
            sets = expand_sets(parsed.get("sets") or [], db)
            if not sets:
                warnings.append("Could not extract strength sets — try 'bench press 3x8 at 60kg'")
        except Exception as e:
            warnings.append(f"Strength parse failed: {e}")

    # Food via Nutrition API
    if intent in ("food", "mixed") or food_text:
        try:
            nix_foods = await nutrition_api.natural_nutrients(food_text or text)
            if not nix_foods:
                warnings.append("Nutrition API returned no foods — check wording")
            for f in nix_foods:
                foods.append(
                    DraftFood(
                        food_name=f.get("food_name") or "food",
                        calories=float(f.get("nf_calories") or 0),
                        protein=float(f.get("nf_protein") or 0),
                        carbs=float(f.get("nf_total_carbohydrate") or 0),
                        fat=float(f.get("nf_total_fat") or 0),
                        quantity=f.get("serving_qty"),
                        unit=f.get("serving_unit"),
                        confidence=0.9 if f.get("nf_calories") is not None else 0.4,
                    )
                )
        except nutrition_api.NutritionAPIError as e:
            warnings.append(str(e))
        except Exception as e:
            warnings.append(f"Food parse failed: {e}")

    # Cardio / burn via Nutrition API
    burn_query = cardio_text
    if intent in ("cardio", "mixed") or cardio_text:
        burn_query = cardio_text or text
    # Also estimate burn for pure strength sessions if we have a query
    if not burn_query and intent == "strength" and strength_text:
        burn_query = strength_text

    if burn_query and profile:
        try:
            exercises = await nutrition_api.natural_exercise(
                burn_query,
                gender=profile.gender or "male",
                weight_kg=profile.weight_kg,
                height_cm=profile.height_cm,
                age=profile.age,
            )
            for ex in exercises:
                cals = float(ex.get("nf_calories") or 0)
                calories_burned += cals
                duration = None
                if ex.get("duration_min") is not None:
                    duration = float(ex["duration_min"])
                cardio.append(
                    DraftCardio(
                        name=ex.get("name") or "activity",
                        duration_min=duration,
                        calories=cals,
                        confidence=0.85 if cals else 0.4,
                    )
                )
            if not exercises and intent in ("cardio", "mixed"):
                warnings.append("No cardio calories returned — try 'ran 20 minutes'")
        except nutrition_api.NutritionAPIError as e:
            warnings.append(str(e))
        except Exception as e:
            warnings.append(f"Exercise calorie parse failed: {e}")
    elif burn_query and not profile:
        warnings.append("Complete your profile (weight/height/age) for calorie burn estimates")

    # Overall confidence: min of component confidences when present
    confs = [base_conf]
    if sets:
        confs.append(min(s.match_confidence for s in sets) if sets else 0)
    if foods:
        confs.append(min(f.confidence for f in foods))
    if cardio:
        confs.append(min(c.confidence for c in cardio))
    overall = min(confs) if confs else 0.0

    if any(s.needs_confirm for s in sets):
        warnings.append("Some exercises need confirmation — pick from suggestions")

    return ParseResponse(
        intent=intent,
        confidence=round(overall, 3),
        sets=sets,
        foods=foods,
        cardio=cardio,
        calories_burned=round(calories_burned, 1),
        warnings=warnings,
        raw_query=text,
    )
