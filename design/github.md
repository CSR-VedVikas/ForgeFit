repo: CSR-VedVikas/ForgeFit
branch: main
path: frontend/src

## Last sync

date: 2026-07-28 (track A complete; nutrition + courses added)

### Updated in this project

- Recreated all 10 current screens from `frontend/src` at pixel fidelity (dark + lime baseline) with a written audit.
- Reinvented the UI on the Modernist design system, approved on the **ink ground**: `#171615` ground, `#ff563c` accent, Archivo, 0px radius, 2px rules, caps exercise names, Lucide icons in the tab bar.
- Live Workout prototype: numpad sheet with plate steppers, last-session prefill, one-tap logging, auto rest timer, session summary.
- Routine builder: picker-first flow, add/remove toggle, reorder, sets/kg/reps steppers, live cost strip; routines are real state feeding Train and Today.
- Settings: biometric + calorie steppers, segmented rest / units / plate / privacy rows. Rest default and plate increment are passed as props into the session sheet, so changing them changes the live workout.
- Record moment (replaces `components/PRCelebration.jsx`): logging above an exercise's previous best turns the session footer into a red poster panel — new weight at display size, previous best, gain, prior sets charted, self-retiring on a 6s rule. Weight unit follows Settings.
- Removed the superseded light-ground builds; the ink build is the single source of truth per screen.
- Records: all three types `pr_engine` keeps (max_weight, max_volume, max_reps) are detected and stack on one panel; they report up to the app root keyed by exercise+type, so Today's records list and the You count update from the live session.
- New screens: Fuel (day nutrition, behind Today's calorie tiles, hands off to Smart log to add — matches `FoodLog.query_text`), Privacy & data (what is stored + retention, export, two-step deletion), and password reset (request / sent / new password).
- The reset flow is designed so finding S1 cannot recur: the confirmation is identical whether or not the account exists and no token is ever shown.
- Fuel v2: portion editor (servings and grams over one value), per-meal calorie targets, water (35 ml/kg), recents/favourites/saved meals, repeat-yesterday, weigh-in trend with goal adherence, and a barcode flow with a pre-permission explainer.
- Courses: training presets with a duration (weeks, days/week, weekly load step). Finishing a session advances the course; Today's kicker and the session name read from it.

## Schema gaps — closed by migration 0003 (21 Sep 2026)

| Gap | Was | Now |
| --- | --- | --- |
| N1 | `food_logs` had no quantity/unit; parsed then dropped on save | `food_logs.quantity`, `.unit`; `FoodLogCreate` carries both |
| N2 | No water log table | `water_logs`; `POST /api/nutrition/water`; `daily` returns `water_ml` + `water_goal_ml` (35 ml/kg) |
| N3 | `Profile.weight_kg` was a single current value | `weigh_ins`, backfilled from profiles; a changed `weight_kg` appends a row; `GET /api/profile/weigh-ins` |
| N4 | `Routine` had no time dimension | `courses` (3 seeded presets) + `course_enrolments`; `/api/courses/*`; finishing a workout advances the cursor |
| N5 | Barcode needed the provider's product endpoint | `nutrition_api.product_by_barcode()`; `GET /api/nutrition/barcode/{upc}` |
| R1 | Builder prescription had nowhere to persist | `routine_exercises.target_weight_kg`, `.target_reps` (nullable — no target is not zero) |
| W1 | `POST /api/workouts` had no idempotency key | `workout_sessions.client_id`, unique per user; a replay returns the original row |

19 tests in `backend/tests/test_schema_gaps.py`, one or more per gap.

## Screen map

| Project screen | Built from |
| --- | --- |
| ForgeFit - Current UI · 01 Landing | frontend/src/pages/Landing.jsx, components/QuoteRotator.jsx, styles.css |
| ForgeFit - Current UI · 02 Auth | frontend/src/pages/Auth.jsx, styles.css |
| ForgeFit - Current UI · 03 Dashboard | frontend/src/pages/Dashboard.jsx, components/WorkoutCard.jsx, components/AppShell.jsx |
| ForgeFit - Current UI · 04–05 Live Workout | frontend/src/pages/LiveWorkout.jsx |
| ForgeFit - Current UI · 06 Smart Log | frontend/src/pages/SmartLog.jsx |
| ForgeFit - Current UI · 07–08 Library | frontend/src/pages/Library.jsx |
| ForgeFit - Current UI · 09 Profile | frontend/src/pages/Profile.jsx |
| ForgeFit - Current UI · 10 Muscle map | frontend/src/pages/Heatmap.jsx |
| LiveWorkout-Ink (approved) | frontend/src/pages/LiveWorkout.jsx (session view) |
| LiveWorkout-Ink · Record moment | components/PRCelebration.jsx (replaced) |
| ForgeFitApp-Ink (approved) · Today | frontend/src/pages/Dashboard.jsx, components/WorkoutCard.jsx |
| ForgeFitApp-Ink · Smart log | frontend/src/pages/SmartLog.jsx |
| ForgeFitApp-Ink · Train | frontend/src/pages/LiveWorkout.jsx (hub) |
| ForgeFitApp-Ink · Routine builder | frontend/src/pages/LiveWorkout.jsx (routine create/edit) |
| ForgeFitApp-Ink · Library | frontend/src/pages/Library.jsx |
| ForgeFitApp-Ink · You | frontend/src/pages/Profile.jsx |
| ForgeFitApp-Ink · Settings | frontend/src/pages/Profile.jsx (settings), backend user/biometrics fields |
| ForgeFitApp-Ink · Muscle map | frontend/src/pages/Heatmap.jsx |
| ForgeFitEntry-Ink | frontend/src/pages/Landing.jsx, pages/Auth.jsx |
| ForgeFitEntry-Ink · Reset flow | frontend/src/pages/ForgotPassword.jsx (redesigned; token must not be returned) |
| ForgeFitApp-Ink · Fuel | routers/nutrition.py, services/nutrition_api.py, pages/Nutrition.jsx |
| ForgeFitApp-Ink · Portion editor / add-food / barcode | routers/nutrition.py (needs qty+unit columns) |
| ForgeFitApp-Ink · Courses | routers/routines.py (needs course + enrolment tables) |
| ForgeFitApp-Ink · Privacy & data | routers/profile.py, pages/Privacy.jsx |
| assets/ex-*.jpg | exercises-dataset-main/images |

## Not yet designed

- Store-app shell: packaging, secure token storage, biometric lock (confirmed in scope 28 Jul)
- Offline logging queue UI (confirmed launch scope — shapes the session model)

## Not yet wired

- Wiring the approved UI into `frontend/src` (prototype is standalone, data mocked) — auth, exercise catalog, session create/log-set, smart-log parsing, routines CRUD, settings persistence

## Sync history

- 2026-07-27 — recreated all 10 current screens, then the Modernist redesign through routine builder + settings.
- 2026-09-21 — migration 0003 closed N1–N5, R1, W1. `frontend-api/endpoints.js` updated with the new routes. Wiring is unblocked on the schema side.
