"""Food data: USDA FoodData Central + Open Food Facts (services/food_sources.py),
the Smart Log food pipeline (nlp_router.lookup_foods), and the barcode endpoint.

No test touches the network. The ranking cases are the real failures seen
while probing the live APIs: USDA's raw top hits for "egg" included a
Snickers Egg and Eggs Benedict.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import FoodLog
from app.services import food_sources as fs
from app.services import nlp_router, openai_nlp
from app.services.food_sources import Candidate

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def cand(name, source="usda", brand="", kcal=100.0, generic=None, serving_g=None, ref=None):
    return Candidate(
        source=source, ref=ref or f"{source}-{name}", name=name, brand=brand,
        kcal_100g=kcal, protein_100g=10, carbs_100g=20, fat_100g=5,
        serving_g=serving_g, generic=(source == "usda" and not brand) if generic is None else generic,
    )


@pytest.fixture(autouse=True)
def _fresh_cache():
    fs.clear_cache()
    yield
    fs.clear_cache()


# ── ranking ──────────────────────────────────────────────────────────

def top(query, cands):
    return fs.rank(query, cands)[0].name


def test_egg_prefers_the_plain_egg_over_products_and_dishes():
    cands = [
        cand("EGG", brand="Snickers", kcal=513),
        cand("Egg, Benedict"),
        cand("Bagels, egg"),
        cand("Egg burrito"),
        cand("Eggs, Grade A, Large, egg white"),
        cand("Eggs, Grade A, Large, egg whole"),
        cand("Medium Eggs", source="off", brand="The Happy Egg Co"),
    ]
    assert top("egg", cands) == "Eggs, Grade A, Large, egg whole"


def test_plural_and_neutral_descriptors_do_not_cost_points():
    cands = [cand("Banana chips"), cand("Banana split"), cand("Bananas, raw"), cand("Banana pudding")]
    assert top("banana", cands) == "Bananas, raw"


def test_preparation_the_user_did_not_ask_for_is_penalised():
    cands = [cand("Chicken breast tenders, breaded, cooked, microwaved"),
             cand("Chicken, broilers or fryers, breast, meat only, cooked, roasted")]
    assert "breaded" not in top("chicken breast cooked", cands)


def test_naming_a_brand_prefers_that_brand():
    cands = [cand("Yogurt, Greek, plain, nonfat"), cand("Chobani Greek yogurt", source="off", brand="Chobani")]
    assert top("chobani greek yogurt", cands) == "Chobani Greek yogurt"


def test_a_brand_that_merely_contains_the_food_is_not_a_named_brand():
    cands = [cand("Oats", source="off", brand="Quaker Oats"), cand("Oats, raw")]
    assert top("oats", cands) == "Oats, raw"


def test_both_sources_stay_visible_even_when_one_scores_higher():
    usda = [cand(f"Rice, white, cooked, variant {i}") for i in range(10)]
    # Relevant but lower-scoring (branded) — they must still get slots.
    off = [cand("Cooked white rice", source="off", brand="X"), cand("White rice, cooked", source="off", brand="Y")]
    ranked = fs.rank("white rice cooked", usda + off)
    assert {c.source for c in ranked} == {"usda", "off"}
    assert len(ranked) == 8


def test_duplicate_listings_collapse():
    dupes = [cand("GREEK YOGURT", source="off", brand="Heinen's", ref=str(i)) for i in range(4)]
    assert len(fs.rank("greek yogurt", dupes)) == 1


# ── provider parsing ─────────────────────────────────────────────────

def test_usda_kcal_falls_back_to_atwater_then_kilojoules():
    atwater = {"description": "X", "fdcId": 1, "foodNutrients": [
        {"nutrientNumber": "958", "value": 140, "unitName": "KCAL"},
        {"nutrientNumber": "203", "value": 12, "unitName": "G"}]}
    assert fs._usda_candidate(atwater, generic=True).kcal_100g == 140
    kj = {"description": "Y", "fdcId": 2, "foodNutrients": [{"nutrientNumber": "268", "value": 418.4, "unitName": "kJ"}]}
    assert fs._usda_candidate(kj, generic=True).kcal_100g == 100
    assert fs._usda_candidate({"description": "Z", "foodNutrients": []}, generic=True) is None


def test_usda_serving_skips_quantity_not_specified():
    food = {"description": "Egg", "fdcId": 3,
            "foodNutrients": [{"nutrientNumber": "208", "value": 143, "unitName": "KCAL"}],
            "foodMeasures": [{"disseminationText": "Quantity not specified", "gramWeight": 155},
                             {"disseminationText": "1 large", "gramWeight": 50}]}
    c = fs._usda_candidate(food, generic=True)
    assert (c.serving_g, c.serving_label) == (50, "1 large")


def test_off_parses_brand_lists_and_kilojoules():
    c = fs._off_candidate({"code": "1", "product_name": "Bar", "brands": ["Acme", "Other"],
                           "nutriments": {"energy_100g": 2092, "proteins_100g": "20"}, "serving_quantity": "40"})
    assert (c.brand, round(c.kcal_100g), c.protein_100g, c.serving_g) == ("Acme", 500, 20.0, 40.0)
    assert fs._off_candidate({"product_name": "No energy", "nutriments": {}}) is None


# ── search orchestration ─────────────────────────────────────────────

def test_one_source_down_still_returns_the_other_and_is_not_cached(monkeypatch):
    monkeypatch.setattr(fs, "get_settings", lambda: type("S", (), {"usda_fdc_api_key": "k"})())
    async def off_ok(client, q):
        return [cand("Banana", source="off", brand="Fairtrade")]
    async def usda_down(client, q):
        raise fs.httpx.ConnectError("down")
    monkeypatch.setattr(fs, "search_off", off_ok)
    monkeypatch.setattr(fs, "search_usda", usda_down)

    found, warnings = asyncio.run(fs.search("banana"))
    assert [c.source for c in found] == ["off"]
    assert warnings and "USDA" in warnings[0]
    assert fs._cache_get("s:banana") is None  # a degraded answer is not remembered


def test_without_a_usda_key_only_open_food_facts_is_asked(monkeypatch):
    monkeypatch.setattr(fs, "get_settings", lambda: type("S", (), {"usda_fdc_api_key": ""})())
    called = []
    async def off_ok(client, q):
        return [cand("Banana", source="off")]
    async def usda(client, q):
        called.append(q)
        return []
    monkeypatch.setattr(fs, "search_off", off_ok)
    monkeypatch.setattr(fs, "search_usda", usda)
    found, warnings = asyncio.run(fs.search("banana"))
    assert found and not warnings and not called


def test_results_are_cached(monkeypatch):
    monkeypatch.setattr(fs, "get_settings", lambda: type("S", (), {"usda_fdc_api_key": ""})())
    calls = []
    async def off_ok(client, q):
        calls.append(q)
        return [cand("Banana", source="off")]
    monkeypatch.setattr(fs, "search_off", off_ok)
    asyncio.run(fs.search("Banana"))
    asyncio.run(fs.search("banana "))
    assert len(calls) == 1


def test_barcode_tries_open_food_facts_then_usda(monkeypatch):
    monkeypatch.setattr(fs, "get_settings", lambda: type("S", (), {"usda_fdc_api_key": "k"})())
    order = []
    async def off_miss(client, code):
        order.append("off")
        return None
    async def usda_hit(client, code):
        order.append("usda")
        return cand("Protein bar", brand="Acme", generic=False)
    monkeypatch.setattr(fs, "barcode_off", off_miss)
    monkeypatch.setattr(fs, "barcode_usda", usda_hit)
    found, _ = asyncio.run(fs.lookup_barcode("012345678905"))
    assert order == ["off", "usda"] and found.name == "Protein bar"


# ── grams and drafts ─────────────────────────────────────────────────

def test_grams_explicit_then_portion_then_100():
    c = cand("Egg", serving_g=50)
    assert fs.resolve_grams(c, 120, 2) == 120  # stated or estimated weight wins
    assert fs.resolve_grams(c, None, 2) == 100  # 2 x the 50 g portion
    assert fs.resolve_grams(cand("Rice"), None, None) == 100


def test_draft_scales_per_100g_values():
    d = fs.to_draft([cand("Rice", kcal=130)], 0, 200, query="rice")
    assert (d.calories, d.protein, d.carbs, d.fat, d.grams) == (260, 20, 40, 10, 200)
    assert d.options[0].kcal_100g == 130  # unscaled, so the UI can rescale


# ── the Smart Log pipeline ───────────────────────────────────────────

def _stub_pipeline(monkeypatch, items, results, picks):
    async def parse(text):
        return items
    async def search(q):
        return results.get(q, ([], []))
    async def pick(xs):
        return picks(xs)
    monkeypatch.setattr(openai_nlp, "parse_food_items", parse)
    monkeypatch.setattr(fs, "search", search)
    monkeypatch.setattr(openai_nlp, "pick_food_matches", pick)


def test_lookup_uses_the_model_pick_and_keeps_every_option(monkeypatch):
    options = [cand("Bagels, egg"), cand("Egg, whole, raw", serving_g=50)]
    _stub_pipeline(monkeypatch, [{"name": "egg", "quantity": 2, "unit": None, "grams": None}],
                   {"egg": (options, [])}, picks=lambda xs: [1])
    drafts, warnings = asyncio.run(nlp_router.lookup_foods("2 eggs"))
    d = drafts[0]
    assert d.food_name == "Egg, whole, raw" and d.selected == 1 and len(d.options) == 2
    assert d.grams == 100 and d.confidence == 0.9 and not warnings


def test_lookup_keeps_local_ranking_when_the_model_declines(monkeypatch):
    options = [cand("Banana, raw"), cand("Banana chips")]
    for c in options:
        c.score = 90
    _stub_pipeline(monkeypatch, [{"name": "banana", "quantity": 1, "unit": None, "grams": 120}],
                   {"banana": (options, [])}, picks=lambda xs: [None])
    d = asyncio.run(nlp_router.lookup_foods("a banana"))[0][0]
    assert d.selected == 0 and d.food_name == "Banana, raw" and d.confidence == 0.6


def test_lookup_reports_items_with_no_match(monkeypatch):
    _stub_pipeline(monkeypatch, [{"name": "zzzz"}, {"name": "rice", "grams": 150}],
                   {"rice": ([cand("Rice, white, cooked")], [])}, picks=lambda xs: [0])
    drafts, warnings = asyncio.run(nlp_router.lookup_foods("zzzz and rice"))
    assert [d.query for d in drafts] == ["rice"]
    assert any("zzzz" in w for w in warnings)


def test_heuristic_splitter_handles_counts_weights_and_fractions():
    items = openai_nlp._heuristic_food_items("ate 2 eggs, 150g rice, half a cup of oats and 1/2 avocado")
    got = [(i["name"], i["quantity"], i["grams"]) for i in items]
    assert got == [("eggs", 2.0, None), ("rice", 150.0, 150.0), ("oats", 0.5, None), ("avocado", 0.5, None)]


# ── endpoints ────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = TestingSessionLocal()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def override():
        yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth(client):
    r = client.post("/api/auth/register", json={"email": "f@test.com", "password": "password1"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_barcode_endpoint_returns_a_draft_at_one_serving(client, auth, monkeypatch):
    async def hit(code):
        return cand("Nutella", source="off", brand="Ferrero", kcal=539, serving_g=15, ref=code), []
    monkeypatch.setattr(fs, "lookup_barcode", hit)
    r = client.get("/api/nutrition/barcode/3017620422003", headers=auth)
    assert r.status_code == 200
    d = r.json()
    assert (d["source"], d["source_ref"], d["grams"], round(d["calories"])) == ("off", "3017620422003", 15, 81)


def test_barcode_endpoint_is_502_when_every_source_is_down(client, auth, monkeypatch):
    async def down(code):
        return None, ["Open Food Facts is unavailable right now."]
    monkeypatch.setattr(fs, "lookup_barcode", down)
    assert client.get("/api/nutrition/barcode/3017620422003", headers=auth).status_code == 502


def test_food_log_keeps_its_source_for_attribution(client, auth, db):
    r = client.post("/api/nutrition/log", headers=auth, json={
        "food_name": "Nutella", "calories": 81, "quantity": 15, "unit": "g",
        "source": "off", "source_ref": "3017620422003",
    })
    assert r.status_code == 200
    row = db.query(FoodLog).one()
    assert (row.source, row.source_ref) == ("off", "3017620422003")
    assert r.json()["source"] == "off"


def test_confident_matches_skip_the_model(monkeypatch):
    sure = cand("Banana, raw")
    sure.score = 106
    asked = []
    _stub_pipeline(monkeypatch, [{"name": "banana", "grams": 120}], {"banana": ([sure], [])},
                   picks=lambda xs: asked.append(xs) or [None] * len(xs))
    asyncio.run(nlp_router.lookup_foods("a banana"))
    assert asked == []  # no OpenAI round trip when the local match is certain


def test_items_from_the_classifier_are_reused(monkeypatch):
    async def must_not_parse(text):
        raise AssertionError("second OpenAI call made")
    monkeypatch.setattr(openai_nlp, "parse_food_items", must_not_parse)
    async def search(q):
        c = cand("Egg, whole, raw")
        c.score = 106
        return [c], []
    monkeypatch.setattr(fs, "search", search)
    drafts, _ = asyncio.run(nlp_router.lookup_foods("2 eggs", items=[{"name": "egg", "grams": 100}]))
    assert drafts[0].grams == 100


def test_unrelated_candidates_are_dropped_not_shown():
    ranked = fs.rank("white rice cooked", [
        cand("Rice, white, cooked, no added fat"),
        cand("Rougail saucisses", source="off", brand="Paul & Louise"),
        cand("Coconut chicken korma", source="off", brand="Deep Indian Kitchen"),
    ])
    assert [c.name for c in ranked] == ["Rice, white, cooked, no added fat"]
