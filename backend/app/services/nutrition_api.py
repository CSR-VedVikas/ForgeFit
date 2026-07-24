from typing import Any
import httpx
from ..config import get_settings


class NutritionAPIError(Exception):
    pass


def _candidate_bases(settings) -> list[str]:
    """Prefer 100 Days of Python proxy; only hit Nutritionix if keys look native."""
    configured = settings.nutrition_api_base_url.rstrip("/")
    days_bases = [
        configured,
        "https://app.100daysofpython.dev/services/nutrition/v2",
        "https://app.100daysofpython.dev/services/nutrition/api/v2",
        "https://app.100daysofpython.dev/api/v2",
    ]
    # Classic Nutritionix app ids are short hex without app_ prefix
    native_looking = (
        settings.nutrition_app_id
        and not settings.nutrition_app_id.startswith("app_")
        and not settings.nutrition_app_key.startswith("nix_live_")
    )
    if native_looking:
        days_bases.append("https://trackapi.nutritionix.com/v2")

    seen: set[str] = set()
    return [b for b in days_bases if b and not (b in seen or seen.add(b))]


async def _post_nutrition(path: str, body: dict) -> dict:
    """POST to Nutrition API across known base URLs."""
    settings = get_settings()
    if not settings.nutrition_app_id or not settings.nutrition_app_key:
        raise NutritionAPIError("Nutrition API credentials not configured")

    headers = {
        "x-app-id": settings.nutrition_app_id,
        "x-app-key": settings.nutrition_app_key,
        "Content-Type": "application/json",
        "x-remote-user-id": "0",
        "Accept": "application/json",
    }

    errors: list[str] = []
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for base in _candidate_bases(settings):
            url = f"{base}/{path.lstrip('/')}"
            try:
                resp = await client.post(url, headers=headers, json=body)
                if resp.status_code < 400:
                    return resp.json()
                errors.append(f"{url} → {resp.status_code}: {resp.text[:180]}")
            except Exception as e:
                errors.append(f"{url} → {e}")

    hint = (
        " Create a fresh Nutrition app key at "
        "https://app.100daysofpython.dev/services/nutrition/docs and update "
        "NUTRITION_APP_ID / NUTRITION_APP_KEY in backend/.env. "
        "Keys starting with app_/nix_live_ will not work on trackapi.nutritionix.com."
    )
    raise NutritionAPIError("Nutrition API failed. " + " | ".join(errors[-2:]) + hint)


async def natural_nutrients(query: str) -> list[dict[str, Any]]:
    """Parse food text into nutrition items via Nutritionix-compatible API."""
    data = await _post_nutrition("natural/nutrients", {"query": query})
    return data.get("foods") or []


async def natural_exercise(
    query: str,
    *,
    gender: str,
    weight_kg: float,
    height_cm: float,
    age: int,
) -> list[dict[str, Any]]:
    """Estimate exercise calories burned from natural language."""
    body = {
        "query": query,
        "gender": gender,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "age": age,
    }
    data = await _post_nutrition("natural/exercise", body)
    return data.get("exercises") or []
