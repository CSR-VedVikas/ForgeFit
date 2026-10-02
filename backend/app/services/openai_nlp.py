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


# ── food ──────────────────────────────────────────────────────────────
# Food lookup moved to USDA + Open Food Facts, which search one food at a time
# and answer per 100 g. So the sentence is first split into items with an
# amount in grams, and after the search the best candidate is picked per item.

FOOD_ITEMS_SYSTEM = """Split a meal description into individual foods.
Return JSON only:
{"items": [{"name": "plain food name a nutrition database would use",
            "quantity": number or null, "unit": "as the user said it, or null",
            "grams": number — your best estimate of the total edible weight}]}
Keep brand names in "name" when the user gave one ("chobani greek yogurt").
"2 eggs" -> name "egg", quantity 2, unit null, grams 100.
"a bowl of rice" -> name "white rice cooked", quantity 1, unit "bowl", grams 200.
"""

FOOD_PICK_SYSTEM = """For each food a user ate, choose the database entry that
best matches what they most likely meant. Prefer the plain, common form over
dishes, desserts, or flavoured variants unless the user said so. If the user
named a brand, prefer that brand.
Return JSON only: {"picks": [index or null, ...]} — one entry per food, in
order, where index refers to that food's numbered candidates."""

_UNIT_GRAMS = {"g": 1, "gram": 1, "grams": 1, "kg": 1000, "ml": 1, "l": 1000, "oz": 28.35, "lb": 453.6}
_NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "half": 0.5, "half a": 0.5}


async def parse_food_items(text: str) -> list[dict[str, Any]]:
    client = _client()
    if client:
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": FOOD_ITEMS_SYSTEM},
                    {"role": "user", "content": text},
                ],
            )
            items = json.loads(resp.choices[0].message.content or "{}").get("items") or []
            items = [i for i in items if isinstance(i, dict) and (i.get("name") or "").strip()]
            if items:
                return items
        except _FALLBACK_ERRORS as e:
            logger.warning('"openai_fallback":"parse_food_items","error":"%s"', type(e).__name__)
    return _heuristic_food_items(text)


def _heuristic_food_items(text: str) -> list[dict[str, Any]]:
    """Offline splitter for "2 eggs, 150g rice and a banana". It has no idea
    how much an egg weighs, so grams stay null unless the unit is a weight —
    the caller then uses the matched food's household portion."""
    import re

    t = re.sub(r"^\s*(i\s+)?(ate|had|eaten|drank)\s+", "", text.strip(), flags=re.I)
    parts = [p.strip(" .") for p in re.split(r",|\band\b|\bthen\b|\+|;", t, flags=re.I) if p.strip(" .")]
    pattern = re.compile(
        r"^(?P<qty>\d+/\d+|\d+(?:\.\d+)?|half a|an?|one|two|three|four|five|six|half)?\s*"
        r"(?P<unit>g|grams?|kg|ml|l|oz|lb|cups?|tbsp|tsp|slices?|pieces?|bowls?|glass(?:es)?)?\b\s*"
        r"(?:of\s+)?(?P<name>.+)$",
        re.I,
    )
    items = []
    for part in parts:
        m = pattern.match(part)
        if not m or not m.group("name").strip():
            continue
        raw_qty = (m.group("qty") or "").lower()
        if "/" in raw_qty:
            a, b = raw_qty.split("/")
            qty = float(a) / float(b) if float(b) else None
        elif raw_qty:
            qty = _NUMBER_WORDS.get(raw_qty) or float(raw_qty)
        else:
            qty = None
        unit = (m.group("unit") or "").lower() or None
        grams = qty * _UNIT_GRAMS[unit] if qty and unit in _UNIT_GRAMS else None
        items.append({"name": m.group("name").strip(), "quantity": qty, "unit": unit, "grams": grams})
    return items


async def pick_food_matches(items: list[dict[str, Any]]) -> list[int | None]:
    """items: [{"text": what the user said, "candidates": ["name [brand]", ...]}].
    Returns one candidate index (or None) per item. Without OpenAI, or when it
    fails, returns all None and the caller keeps its own ranking."""
    client = _client()
    if not client or not items:
        return [None] * len(items)
    listing = "\n".join(
        f"Food {n}: {it['text']}\n" + "\n".join(f"  {i}. {c}" for i, c in enumerate(it["candidates"]))
        for n, it in enumerate(items)
    )
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": FOOD_PICK_SYSTEM},
                {"role": "user", "content": listing},
            ],
        )
        picks = json.loads(resp.choices[0].message.content or "{}").get("picks") or []
    except _FALLBACK_ERRORS as e:
        logger.warning('"openai_fallback":"pick_food_matches","error":"%s"', type(e).__name__)
        return [None] * len(items)
    out: list[int | None] = []
    for n, it in enumerate(items):
        p = picks[n] if n < len(picks) else None
        out.append(p if isinstance(p, int) and 0 <= p < len(it["candidates"]) else None)
    return out
