"""Food data from two sources, offered side by side.

USDA FoodData Central is strong on plain foods ("egg, whole, raw") and has
household portions ("1 large egg = 50 g"). Open Food Facts is strong on
packaged and branded products and barcodes. Users' habits differ, so a
search queries both and returns one ranked list; the user picks.

Every value is per 100 g. A Candidate is scaled to grams only when it becomes
a DraftFood, so switching between candidates in the UI is pure arithmetic.

Notes from probing the live APIs (Oct 2026), which shaped this file:
- USDA's gateway rejects "(" in a GET query string, and one of its data types
  is literally "Survey (FNDDS)", so searches are POSTs with a JSON body.
- Open Food Facts' legacy /cgi/search.pl returns 503. The newer
  search.openfoodfacts.org service works and returns brands as a list.
- Raw relevance is poor for short queries: USDA's top "egg" hits include a
  Snickers Egg and Eggs Benedict. Hence the local re-ranking here, and an
  OpenAI pick on top of it in nlp_router.

Open Food Facts data is ODbL-licensed: wherever its results are shown, the UI
must say so. Each request identifies the app in its User-Agent, as their API
terms ask.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import asdict, dataclass

import httpx
from rapidfuzz import fuzz

from ..config import get_settings
from ..schemas import DraftFood, FoodOption

USER_AGENT = "ForgeFit/1.2 (+https://github.com/CSR-VedVikas/ForgeFit)"
USDA_SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"
OFF_SEARCH = "https://search.openfoodfacts.org/search"
OFF_PRODUCT = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
OFF_FIELDS = "code,product_name,brands,nutriments,serving_quantity,serving_size"

USDA_GENERIC = ["Foundation", "SR Legacy", "Survey (FNDDS)"]
TIMEOUT = httpx.Timeout(12.0)


@dataclass
class Candidate:
    source: str  # "usda" | "off"
    ref: str  # USDA fdcId or Open Food Facts barcode
    name: str
    brand: str
    kcal_100g: float
    protein_100g: float
    carbs_100g: float
    fat_100g: float
    serving_g: float | None = None
    serving_label: str = ""
    generic: bool = False  # USDA Foundation/SR/FNDDS, as opposed to branded
    score: float = 0.0

    def option(self) -> dict:
        d = asdict(self)
        d.pop("generic")
        d.pop("score")
        return d


# ── cache ─────────────────────────────────────────────────────────────
# Food facts change rarely, and Open Food Facts rate-limits searches per IP —
# which, behind one server, means per deployment. A day of caching keeps
# "banana" and "eggs" from spending that budget over and over.

_CACHE_TTL = 24 * 3600
_CACHE_MAX = 2000
_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str):
    hit = _cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    _cache.pop(key, None)
    return None


def _cache_put(key: str, value) -> None:
    if len(_cache) >= _CACHE_MAX:
        # Drop the oldest tenth rather than one entry per insert.
        for k in sorted(_cache, key=lambda k: _cache[k][0])[: _CACHE_MAX // 10]:
            _cache.pop(k, None)
    _cache[key] = (time.monotonic() + _CACHE_TTL, value)


def clear_cache() -> None:
    _cache.clear()


# ── USDA ──────────────────────────────────────────────────────────────

def _usda_nutrients(food: dict) -> dict[str, float] | None:
    by_num = {n.get("nutrientNumber"): n for n in food.get("foodNutrients") or []}

    def val(num):
        n = by_num.get(num)
        return float(n["value"]) if n and n.get("value") is not None else None

    # 208 is kcal. Foundation foods sometimes carry only the Atwater figures
    # (958 specific, 957 general) or kJ (268).
    kcal = val("208")
    if kcal is None or (by_num.get("208", {}).get("unitName") or "").upper() != "KCAL":
        kcal = val("958") or val("957")
        if kcal is None and val("268") is not None:
            kcal = val("268") / 4.184
    if kcal is None:
        return None
    return {
        "kcal_100g": round(kcal, 1),
        "protein_100g": round(val("203") or 0.0, 2),
        "fat_100g": round(val("204") or 0.0, 2),
        "carbs_100g": round(val("205") or 0.0, 2),
    }


def _usda_serving(food: dict) -> tuple[float | None, str]:
    unit = (food.get("servingSizeUnit") or "").lower()
    if food.get("servingSize") and unit in ("g", "grm", "ml", "mlt"):
        label = (food.get("householdServingFullText") or "").strip().lower()
        return round(float(food["servingSize"]), 1), label or f"{food['servingSize']:g} g"
    for m in food.get("foodMeasures") or []:
        text = (m.get("disseminationText") or "").strip()
        if m.get("gramWeight") and text and "not specified" not in text.lower():
            return round(float(m["gramWeight"]), 1), text
    return None, ""


def _usda_candidate(food: dict, generic: bool) -> Candidate | None:
    nut = _usda_nutrients(food)
    if not nut:
        return None
    serving_g, serving_label = _usda_serving(food)
    brand = (food.get("brandName") or food.get("brandOwner") or "").strip()
    return Candidate(
        source="usda", ref=str(food.get("fdcId")), name=(food.get("description") or "").strip(),
        brand=brand.title() if brand.isupper() else brand, serving_g=serving_g,
        serving_label=serving_label, generic=generic, **nut,
    )


async def _usda_post(client: httpx.AsyncClient, body: dict) -> list[dict]:
    key = get_settings().usda_fdc_api_key
    resp = await client.post(USDA_SEARCH, params={"api_key": key}, json=body)
    resp.raise_for_status()
    return resp.json().get("foods") or []


async def search_usda(client: httpx.AsyncClient, query: str) -> list[Candidate]:
    # Generic foods, plus a few branded hits for "kellogg's cornflakes"-style
    # queries. Two requests, issued together: sequentially they cost ~2.4 s.
    generic, branded = await asyncio.gather(
        _usda_post(client, {"query": query, "pageSize": 25, "dataType": USDA_GENERIC}),
        _usda_post(client, {"query": query, "pageSize": 5, "dataType": ["Branded"]}),
    )
    out = [_usda_candidate(f, generic=True) for f in generic]
    out += [_usda_candidate(f, generic=False) for f in branded]
    return [c for c in out if c]


async def barcode_usda(client: httpx.AsyncClient, code: str) -> Candidate | None:
    foods = await _usda_post(client, {"query": code, "pageSize": 5, "dataType": ["Branded"]})
    want = code.lstrip("0")
    for f in foods:
        if (f.get("gtinUpc") or "").lstrip("0") == want:
            return _usda_candidate(f, generic=False)
    return None


# ── Open Food Facts ───────────────────────────────────────────────────

def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _off_candidate(p: dict) -> Candidate | None:
    n = p.get("nutriments") or {}
    kcal = _num(n.get("energy-kcal_100g"))
    if kcal is None and _num(n.get("energy_100g")) is not None:
        kcal = _num(n.get("energy_100g")) / 4.184  # kJ
    name = (p.get("product_name") or "").strip()
    if kcal is None or not name:
        return None
    brands = p.get("brands") or ""
    if isinstance(brands, list):
        brands = ", ".join(b for b in brands if b)
    serving_g = _num(p.get("serving_quantity"))
    return Candidate(
        source="off", ref=str(p.get("code") or ""), name=name, brand=brands.split(",")[0].strip(),
        kcal_100g=round(kcal, 1), protein_100g=round(_num(n.get("proteins_100g")) or 0.0, 2),
        carbs_100g=round(_num(n.get("carbohydrates_100g")) or 0.0, 2),
        fat_100g=round(_num(n.get("fat_100g")) or 0.0, 2),
        serving_g=round(serving_g, 1) if serving_g else None,
        serving_label=(p.get("serving_size") or "").strip(),
    )


async def search_off(client: httpx.AsyncClient, query: str) -> list[Candidate]:
    resp = await client.get(OFF_SEARCH, params={"q": query, "page_size": 10, "fields": OFF_FIELDS, "langs": "en"})
    resp.raise_for_status()
    return [c for c in (_off_candidate(p) for p in resp.json().get("hits") or []) if c]


async def barcode_off(client: httpx.AsyncClient, code: str) -> Candidate | None:
    resp = await client.get(OFF_PRODUCT.format(code=code), params={"fields": OFF_FIELDS})
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != 1:
        return None
    return _off_candidate({**(data.get("product") or {}), "code": data.get("code") or code})


# ── ranking ───────────────────────────────────────────────────────────

_WORD = re.compile(r"[a-z]+")

# Words that change what a food *is*. A match carrying one the user did not
# type is usually wrong: "chicken breast cooked" is not "...breaded,
# microwaved", and "banana" is not "Banana pudding".
_TRANSFORMS = {
    "breaded", "battered", "fried", "microwaved", "candied", "frosted", "glazed",
    "sweetened", "dessert", "pudding", "pie", "cake", "cupcake", "cookie", "candy",
    "chocolate", "benedict", "bagel", "sandwich", "sauce", "soup", "salad",
    "casserole", "substitute", "imitation", "powder", "dried", "dehydrated",
    "flavored", "babyfood", "chip", "nectar", "split", "burrito", "taquito",
    "quesadilla", "congee", "deviled", "creamed",
}
# Descriptors that narrow a food without changing it. Not penalised, so
# "Bananas, raw" is as good a match for "banana" as a bare "Banana".
_NEUTRAL = {
    "raw", "whole", "fresh", "plain", "regular", "large", "medium", "small",
    "grade", "enriched", "unenriched", "boneless", "skinless", "meat", "only",
    "no", "added", "fat", "nfs", "ns", "cooked", "edible", "portion",
}
_FILLER = {"and", "or", "with", "without", "of", "the", "a", "an", "in", "as", "to", "made"}


def _tokens(text: str) -> set[str]:
    out = set()
    for w in _WORD.findall(text.lower()):
        if len(w) > 3 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out - _FILLER


def score(query: str, c: Candidate) -> float:
    """Higher is better; 100 is "covers the query, adds nothing".

    USDA names foods as "Food, descriptor, descriptor". So the first segment
    is what the food *is* and gets strict treatment; later segments only
    narrow it. Open Food Facts names are free text and are treated as all
    head, which is why its extra words cost more.
    """
    q = _tokens(query)
    if not q:
        return 0.0
    name = _tokens(c.name)
    head = _tokens(c.name.split(",")[0]) if c.source == "usda" else name
    tail = name - head

    s = 100.0 * len(q & name) / len(q)  # how much of the query it covers
    if not (q & head):
        s -= 30  # the query's food is not the subject: "Bagels, egg"
    s -= 12 * len(head - q - _NEUTRAL)  # a different dish: "Egg burrito"
    s -= 2 * len(tail - q - _NEUTRAL)  # a narrower variant: "egg white"
    for seg in c.name.lower().split(",")[1:]:
        if seg.strip().startswith("with "):
            s -= 8 * len(_tokens(seg) - q)  # mixed in: "Yogurt, Greek, with oats"
    if (name - q) & _TRANSFORMS:
        s -= 20

    brand = _tokens(c.brand)
    # Named the brand = the query mentions it *and* a food beyond it. Without
    # the second half, "egg" would reward "The Happy Egg Co" and "oats" would
    # reward "Quaker Oats" — brands that merely contain the food's name.
    if brand & q and q - brand:
        s += 15
    elif c.generic:
        s += 6  # otherwise a generic food beats somebody's product
    else:
        s -= 6
    return round(s, 2)


MIN_SCORE = 50.0


def rank(query: str, candidates: list[Candidate], limit: int = 8) -> list[Candidate]:
    seen: set = set()
    unique = []
    for c in candidates:
        # Stores list one product many times under different codes.
        key = (c.source, c.name.lower(), c.brand.lower(), round(c.kcal_100g))
        if key not in seen:
            seen.add(key)
            c.score = score(query, c)
            unique.append(c)
    # A candidate that shares nothing with the query is noise, not a choice:
    # Open Food Facts answered "white rice cooked" with a sausage stew and a
    # chicken korma. Better an empty slot than a wrong option.
    unique = [c for c in unique if c.score >= MIN_SCORE]
    unique.sort(key=lambda c: c.score, reverse=True)
    # Keep both sources visible — users choose between them — by reserving the
    # top two of each, then filling the remaining slots purely by score.
    reserved = [c for c in unique if c.source == "usda"][:2] + [c for c in unique if c.source == "off"][:2]
    rest = [c for c in unique if c not in reserved]
    picked = reserved + rest[: max(0, limit - len(reserved))]
    return sorted(picked, key=lambda c: c.score, reverse=True)[:limit]


# ── public API ────────────────────────────────────────────────────────

def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


async def search(query: str) -> tuple[list[Candidate], list[str]]:
    """Ranked candidates from both sources, and a warning per source that
    failed. One source down still returns the other's results."""
    query = " ".join(query.split())[:80]
    cached = _cache_get(f"s:{query.lower()}")
    if cached is not None:
        return list(cached), []

    warnings: list[str] = []
    have_usda = bool(get_settings().usda_fdc_api_key)
    async with _client() as client:
        tasks = [search_off(client, query)]
        if have_usda:
            tasks.append(search_usda(client, query))
        results = await asyncio.gather(*tasks, return_exceptions=True)

    found: list[Candidate] = []
    names = ["Open Food Facts", "USDA"]
    for name, res in zip(names, results):
        if isinstance(res, Exception):
            warnings.append(f"{name} is unavailable right now; showing other results.")
        else:
            found += res

    ranked = rank(query, found)
    if not warnings:  # never cache a degraded answer
        _cache_put(f"s:{query.lower()}", ranked)
    return ranked, warnings


async def lookup_barcode(code: str) -> tuple[Candidate | None, list[str]]:
    """Open Food Facts first (its strength), USDA Branded as the fallback."""
    cached = _cache_get(f"b:{code}")
    if cached is not None:
        return cached, []
    warnings: list[str] = []
    found = None
    async with _client() as client:
        try:
            found = await barcode_off(client, code)
        except httpx.HTTPError:
            warnings.append("Open Food Facts is unavailable right now.")
        if not found and get_settings().usda_fdc_api_key:
            try:
                found = await barcode_usda(client, code)
            except httpx.HTTPError:
                warnings.append("USDA is unavailable right now.")
    if found and not warnings:
        _cache_put(f"b:{code}", found)
    return found, warnings


# ── drafts ────────────────────────────────────────────────────────────

def resolve_grams(cand: Candidate, grams: float | None, quantity: float | None) -> float:
    """An explicit or estimated weight wins; else the food's own portion times
    the count ("2 eggs" x 50 g); else 100 g per unit. Always editable."""
    if grams:
        return round(float(grams), 1)
    if cand.serving_g:
        return round(cand.serving_g * (quantity or 1), 1)
    return round(100.0 * (quantity or 1), 1)


def to_draft(
    options: list[Candidate], selected: int, grams: float, *, query: str = "",
    quantity: float | None = None, unit: str | None = None, confidence: float = 0.8,
) -> DraftFood:
    c = options[selected]
    k = grams / 100.0
    return DraftFood(
        food_name=c.name, brand=c.brand,
        calories=round(c.kcal_100g * k, 1), protein=round(c.protein_100g * k, 1),
        carbs=round(c.carbs_100g * k, 1), fat=round(c.fat_100g * k, 1),
        quantity=quantity, unit=unit, confidence=confidence,
        query=query, grams=grams, source=c.source, source_ref=c.ref,
        selected=selected, options=[FoodOption(**o.option()) for o in options],
    )
