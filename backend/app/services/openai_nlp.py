import json
import logging
from typing import Any
from openai import AsyncOpenAI, OpenAIError
from ..config import get_settings

logger = logging.getLogger("forgefit")

# Smart Log must keep working when OpenAI does not: an empty balance (a 429
# insufficient_quota), a revoked key, an outage, or a reply that is not the
# JSON we asked for. The regex parsers below were only used when no key was
# configured, so a configured-but-failing key turned every strength entry into
# "Strength parse failed". Any of these now degrades to the regex parser.
_FALLBACK_ERRORS = (OpenAIError, json.JSONDecodeError, TimeoutError)
_TIMEOUT_S = 15.0

CLASSIFY_SYSTEM = """You classify fitness journal text into intents.
Return JSON only with keys:
- intent: one of "food", "strength", "cardio", "mixed"
- confidence: 0-1
- food_text: substring about food/meals (or "")
- strength_text: substring about weighted/bodyweight strength sets (or "")
- cardio_text: substring about cardio/running/cycling duration (or "")
"""

STRENGTH_SYSTEM = """Extract strength training sets from user text.
Return JSON only:
{
  "sets": [
    {
      "exercise_name": "string — common exercise name",
      "weight_kg": number,
      "reps": number,
      "sets_count": number  // how many sets of this scheme, default 1
    }
  ],
  "confidence": 0-1
}
Convert lb to kg (divide by 2.205). If weight omitted use 0.
Expand "3x8 at 60kg" into sets_count=3, reps=8, weight_kg=60.
"""


def _client() -> AsyncOpenAI | None:
    settings = get_settings()
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your"):
        return None
    return AsyncOpenAI(api_key=settings.openai_api_key, timeout=_TIMEOUT_S, max_retries=1)


async def classify_intent(text: str) -> dict[str, Any]:
    client = _client()
    if not client:
        return _heuristic_classify(text)

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM},
                {"role": "user", "content": text},
            ],
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except _FALLBACK_ERRORS as e:
        logger.warning('"openai_fallback":"classify_intent","error":"%s"', type(e).__name__)
        return _heuristic_classify(text)


async def parse_strength_sets(text: str) -> dict[str, Any]:
    client = _client()
    if not client:
        return _heuristic_strength(text)

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": STRENGTH_SYSTEM},
                {"role": "user", "content": text},
            ],
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except _FALLBACK_ERRORS as e:
        logger.warning('"openai_fallback":"parse_strength_sets","error":"%s"', type(e).__name__)
        return _heuristic_strength(text)


def _heuristic_classify(text: str) -> dict[str, Any]:
    t = text.lower()
    food_words = ["ate", "egg", "oatmeal", "chicken", "rice", "calorie", "breakfast", "lunch", "dinner", "protein"]
    cardio_words = ["ran", "run", "jog", "swim", "bike", "cycle", "walk", "mile", "km", "cardio"]
    strength_words = ["bench", "squat", "deadlift", "press", "curl", "rep", "kg", "lb", "x", "set"]

    has_food = any(w in t for w in food_words)
    has_cardio = any(w in t for w in cardio_words)
    has_strength = any(w in t for w in strength_words) or "x" in t

    kinds = sum([has_food, has_cardio, has_strength])
    if kinds > 1:
        intent = "mixed"
    elif has_food:
        intent = "food"
    elif has_cardio:
        intent = "cardio"
    else:
        intent = "strength"

    return {
        "intent": intent,
        "confidence": 0.55,
        "food_text": text if has_food else "",
        "strength_text": text if has_strength else "",
        "cardio_text": text if has_cardio else "",
    }


def _heuristic_strength(text: str) -> dict[str, Any]:
    """Very small offline parser for patterns like 'bench press 3x8 60kg'."""
    import re

    sets: list[dict] = []
    # name ... NxM ... weight
    pattern = re.compile(
        r"(?P<name>[a-zA-Z][a-zA-Z\s/'-]{2,40}?)\s+(?P<sets>\d+)\s*[x×]\s*(?P<reps>\d+)(?:\s*(?:@|at)?\s*(?P<w>\d+(?:\.\d+)?)\s*(?P<u>kg|lb|lbs)?)?",
        re.I,
    )
    for m in pattern.finditer(text):
        w = float(m.group("w") or 0)
        unit = (m.group("u") or "kg").lower()
        if unit.startswith("lb"):
            w = w / 2.205
        sets.append(
            {
                "exercise_name": m.group("name").strip(),
                "weight_kg": round(w, 2),
                "reps": int(m.group("reps")),
                "sets_count": int(m.group("sets")),
            }
        )
    return {"sets": sets, "confidence": 0.5 if sets else 0.2}
