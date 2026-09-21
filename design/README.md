# ForgeFit — redesign

The Modernist "ink" redesign, built in Claude Design. These are standalone
prototypes: they run on fixtures and are **not yet wired** to the API in
`../backend`. The contract they will be wired through is already written and
lives in `frontend-api/`.

## What is here

| Path | What it is |
| --- | --- |
| `_ds/modernist-…/` | The design system — tokens, `styles.css`, component bundle, adherence lint rules |
| `frontend-api/client.js` | The one data layer: auth header, 401 + refresh, retry, `ApiError` |
| `frontend-api/endpoints.js` | Every route the backend exposes, one function each |
| `frontend-api/session-queue.js` | Live session as a local IndexedDB document; flushes on finish |
| `*.dc.html` | Screen prototypes and written docs |
| `support.js`, `doc-page.js` | The Design runtime the prototypes load |
| `android-frame.jsx` | Device frame used for the screenshots |
| `github.md` | Sync record — screen map, schema gaps, what is still unwired |

## Ground rules the redesign settled

- **Ink, not light.** `#171615` ground, `#ff563c` accent, Archivo, 0px radius,
  2px rules. The original UI was light and clinical with weak hierarchy.
- **Caps exercise names**, Lucide icons in the tab bar.
- **The record moment is a footer slab**, not the old full-screen burst —
  it has to be readable mid-set without interrupting the set.

## Running the prototypes

They are static HTML with relative references. Any static server works:

```bash
python -m http.server 8000 --directory design
```

Then open `http://localhost:8000/ForgeFitEntry-Ink.dc.html`.

## Not in this directory yet

The full design export contains seven more prototypes and the image assets:

```
ForgeFitApp-Ink.dc.html        LiveWorkout-Ink.dc.html
ForgeFit - Current UI.dc.html  ForgeFit - Redesign.dc.html
ForgeFit - Completion Plan.dc.html
ForgeFit - Engineering Report.dc.html
ForgeFit - Track B Wiring.dc.html
assets/ex-*.jpg
```

Download the project export from Claude Design, then:

```bash
python design/unpack-export.py ~/Downloads/ForgeFit-export.zip
```

That extracts it here and verifies every prototype's referenced files resolve,
exiting non-zero if anything is still missing — so it is safe to chain with a
commit. Run it with no argument to check the current state without extracting.

`scraps/` and `uploads/` from that export are working residue (PDF page
rasters, pasted screenshots) and are gitignored on purpose.

Until the export is unpacked, `ForgeFitEntry-Ink.dc.html` renders with four
broken images — it references `assets/ex-*.jpg`, which are not committed.

## Media attribution

`assets/ex-*.jpg` are drawn from `../exercises-dataset-main/images` and are
© [Gym visual](https://gymvisual.com/), the same terms as the rest of the
dataset. Do not claim ownership; check licensing before any commercial
redistribution.
