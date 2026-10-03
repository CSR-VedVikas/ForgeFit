"""Exercise calories — the 100 Days of Python nutrition API.

This provider used to supply food data too. In 2026 it moved to
/v1/nutrition and kept only natural/exercise: natural/nutrients and the item
(barcode) lookup now 404. Food comes from services/food_sources.py instead.

The old multi-base fallback loop is gone. It existed to guess between URL
shapes; with one documented base there is nothing to guess, and the loop
hid the real failure behind the last URL it happened to try.
"""

from typing import Any

import httpx

from ..config import get_settings


class NutritionAPIError(Exception):
    pass


async def natural_exercise(
    query: str,
    *,
    gender: str,
    weight_kg: float,
    height_cm: float,
    age: int,
) -> list[dict[str, Any]]:
    """Estimate calories burned from natural language ("ran 30 minutes")."""
    settings = get_settings()
    if not settings.nutrition_app_id or not settings.nutrition_app_key:
        raise NutritionAPIError("Exercise calories are not configured (NUTRITION_APP_ID / NUTRITION_APP_KEY).")

    url = settings.nutrition_api_base_url.rstrip("/") + "/natural/exercise"
    body = {"query": query, "gender": gender, "weight_kg": weight_kg, "height_cm": height_cm, "age": age}
    headers = {
        "x-app-id": settings.nutrition_app_id,
        "x-app-key": settings.nutrition_app_key,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as e:
        raise NutritionAPIError(f"Exercise calorie service unreachable ({type(e).__name__}).") from e

    if resp.status_code == 401:
        raise NutritionAPIError("Exercise calorie service rejected the app credentials.")
    if resp.status_code >= 400:
        raise NutritionAPIError(f"Exercise calorie service returned {resp.status_code}.")
    return resp.json().get("exercises") or []
