# LFPG — Paris Charles de Gaulle, aerodrome layout for MSFS 2024

A toolchain that turns open survey data into an MSFS airport definition, plus a
renderer so the result can be looked at before the simulator is involved.

Built on Linux. **The airport XML has not been compiled or loaded in MSFS**, for
the reason given under *Honest limitations* below. Everything stated here as a
measurement was measured; everything else is flagged as an estimate.

---

## What it produces

| File | What it is |
|---|---|
| `LFPG.xml` | MSFS `bglcomp` airport definition — 4 runways, 6,562 taxiway nodes, 7,212 taxiway paths, 193 taxiway names, 478 parking stands, 74 aprons |
| `lfpg_chart.png` | Plan view of the whole aerodrome |
| `lfpg_3d_sheet.jpg` | Four rendered perspective views |

## The accuracy check

The layout is only worth anything if it is actually to scale, so the runways get
measured back out of the model and compared with the published lengths:

| Runway | Measured | Published | Error | Width |
|---|---|---|---|---|
| 09L/27R | 2696 m | 2700 m | −0.1% | 60 m |
| 09R/27L | 4190 m | 4200 m | −0.2% | 45 m |
| 08L/26R | 4138 m | 4142 m | −0.1% | 45 m |
| 08R/26L | 2696 m | 2700 m | −0.2% | 60 m |

Run `python runways.py` to reproduce it.

Two things this check caught that eyeballing would not have:

- **Runways arrive in pieces.** The source splits a runway wherever another way
  crosses it, so the two long runways first measured ~600 m short. `runways.py`
  chains the segments end to end before measuring. Without the published lengths
  to check against, that error would have shipped.
- **All four runways share one true bearing** — 85.3°, agreeing to within 0.05° —
  even though the north pair is numbered 09/27 and the south pair 08/26. That is
  a genuine CDG convention for telling the two doublets apart, not a data fault,
  so the designators are carried through exactly as tagged.

## Pipeline

```
lfpg.json          Overpass extract (see fetch.sh)
  │
  ├─ geo.py        equirectangular projection about the ARP -> metres
  ├─ runways.py    chain split segments, measure, verify
  │
  ├─ msfs_xml.py   -> LFPG.xml     the sim-format airport definition
  ├─ chart.py      -> plan view
  └─ build3d.py    extrude footprints -> mesh.npz
       └─ render3d.py  z-buffer rasteriser -> perspective views
            └─ sheet.py  contact sheet
```

`render3d.py` is a plain software rasteriser: project, clip against the near
plane, backface-independent z-buffer fill by barycentrics, flat shading. It
exists so the geometry can be checked without the simulator, in the same way a
paintkit `.obj` can be baked and rendered to check a livery.

## Honest limitations

- **Not compiled.** MSFS's `fspackagetool` is Windows-only, so this XML has been
  checked for well-formedness and structure but never fed to the compiler or
  loaded in the sim. Expect to fix schema details on the first build.
- **Stand sizes are uniform.** Every stand is written as `GATE_MEDIUM`,
  radius 24 m, because the source carries no stand size. Real CDG stands run from
  regional up to A380 gates. This is the single most important thing to correct
  before release — as written, heavy aircraft will not park properly.
- **Building heights are mostly estimates.** Where the source gives a height or a
  storey count it is used; otherwise a per-type default (terminal 19 m, hangar
  21 m, tower 64 m). The footprints are real; the heights largely are not.
- **Buildings are massing, not models.** Correct footprint and rough height. No
  glass, roof structure, jetways or signage. Detailed terminals are a different
  and much larger job.
- **`magvar` is a placeholder** (1.4). Set it from the current AIP before release;
  it affects displayed runway headings.
- **Approach lighting, ILS, PAPI and taxiway signage are not generated.**
- Ground markings in the renders are simplified — centreline and edge stripes
  only, no touchdown zone or threshold bars.

## Data and licence

Layout data from **OpenStreetMap**, © OpenStreetMap contributors, available under
the **Open Database Licence (ODbL)**. Anything published from this must carry
that attribution, and the ODbL's share-alike terms apply to derived databases —
worth settling before any public release.

## Reproducing

```sh
sh fetch.sh                 # pulls the Overpass extract
python runways.py           # the accuracy check
python msfs_xml.py          # -> LFPG.xml
python chart.py             # -> lfpg_chart.png
python build3d.py && python render3d.py out.png  <eye xyz> <target xyz> <fov>
```

Needs only `numpy` and `Pillow`.
