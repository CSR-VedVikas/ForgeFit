import json
from pathlib import Path
from sqlalchemy.orm import Session
from ..config import get_settings
from ..models import ExerciseCatalog


def _resolve_exercises_json() -> Path:
    settings = get_settings()
    configured = Path(settings.exercises_json_path)
    if configured.is_absolute() and configured.exists():
        return configured

    backend_dir = Path(__file__).resolve().parent.parent
    project_root = backend_dir.parent
    candidates = [
        configured,
        backend_dir / configured,
        (backend_dir / configured).resolve(),
        project_root / "exercises-dataset-main" / "data" / "exercises.json",
        backend_dir / "exercises-dataset-main" / "data" / "exercises.json",
    ]
    for c in candidates:
        try:
            resolved = c.resolve()
        except OSError:
            continue
        if resolved.exists():
            return resolved
    raise FileNotFoundError(
        f"Exercises JSON not found. Tried: {[str(c) for c in candidates]}"
    )


def seed_exercises(db: Session) -> int:
    """Load exercises from dataset JSON if catalog is empty. Returns count inserted."""
    existing = db.query(ExerciseCatalog).count()
    if existing > 0:
        return 0

    path = _resolve_exercises_json()

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    batch: list[ExerciseCatalog] = []
    for ex in data:
        batch.append(
            ExerciseCatalog(
                id=ex["id"],
                name=ex["name"],
                category=ex.get("category", ""),
                body_part=ex.get("body_part", ""),
                equipment=ex.get("equipment", ""),
                target=ex.get("target", ""),
                muscle_group=ex.get("muscle_group", ""),
                secondary_muscles=ex.get("secondary_muscles") or [],
                instructions_en=(ex.get("instructions") or {}).get("en", ""),
                instruction_steps_en=(ex.get("instruction_steps") or {}).get("en") or [],
                image=ex.get("image", ""),
                gif_url=ex.get("gif_url", ""),
                attribution=ex.get("attribution", ""),
            )
        )
        if len(batch) >= 200:
            db.add_all(batch)
            db.commit()
            batch = []

    if batch:
        db.add_all(batch)
        db.commit()

    return len(data)
