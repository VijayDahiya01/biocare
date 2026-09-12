# Deck generator

Regenerates the BioCore decks from `../BioCore_for_Schools.pptx`, which is the
source of truth for the visual system. The original deck had no generator, so
`ds.py` was reverse-engineered from its XML — palette, type ramp and grid are
taken verbatim from it.

## Run

```sh
../biocore/backend/.venv/Scripts/python.exe build.py
```

Outputs, both written to the repo root:

| File | Contents |
|---|---|
| `BioCore_Product.pptx` | **15 slides, product only** — no partner, no company, no commercials |
| `BioCore_for_Schools_v2.pptx` | the original 13-slide school deck, with the content/layout fixes |
| `BioCore_x_QuickCampus.pptx` | 29 slides — product (1–9), the join (10), partnership (11–15), school deck (16–28), questions (29) |

`esports.py` and `marwah.py` are run on their own, and build from a blank
presentation rather than from the school deck:

```sh
../biocore/backend/.venv/Scripts/python.exe esports.py
../biocore/backend/.venv/Scripts/python.exe marwah.py
```

| File | Contents |
|---|---|
| `BioCore_for_Esports.pptx` | **13 slides** — company-agnostic, written to be forwarded and read unattended |
| `BioCore_for_Marwah_Sports.pptx` | **11 slides** — presented pitch for Marwah Sports Pvt. Ltd. |

The two overlap by design but are aimed differently. The esports deck names no
company and carries its own explanation, because nobody is in the room to give
it: slide 02 says what BioCore is and slide 03 walks the whole chain before any
argument is made, and the last slide ends on a contact placeholder to fill in
before sending. The Marwah deck assumes a presenter, opens on the argument
instead, and swaps the generic four doors for that group's own — SCORE, Mumbai
Ultras, the tournament IPs — before closing on a specific ask.

Both `build()` functions call `ds.renumber`, so the corner numeral follows a
slide's position rather than the name of the builder that drew it. That makes
dropping a slide a one-line edit to `BUILDERS`, which is how the player-integrity
slide (ringers, ban evasion, clean brackets) is currently parked in both decks:
its builder is still there, just not in the list.

`BioCore_for_Schools.pptx` is only ever read, never written.

### The product deck

The product section and the school deck overlapped in five places. `build_product`
keeps whichever slide told each part better and drops the other:

| Topic | Kept | Dropped |
|---|---|---|
| How to deploy | product 08 — four options | school 04 |
| A day in the life | product 05 — one timeline | school 05 + 06 |
| Breadth of use | product 04 — seven workflows | school 07 |
| Open vs controlled | school 08 — two panels | product 06 |
| Privacy | school 09 + 10 | product 07 |

School slide 03 ("The gate stays open") also goes, because product 03 makes the
same three points. Nothing is lost from disk — every dropped slide still lives
in `BioCore_for_Schools_v2.pptx`, and restoring one is a matter of adding its
index back to `order` in `build_product`.

## Files

| File | Role |
|---|---|
| `ds.py` | the design system: palette, fonts, grid, and helpers (`chrome`, `card`, `headline`, `deck`, `footnote`, …) |
| `product.py` | slides 1–10: BioCore as a standalone product, then where QuickCampus fits |
| `partnership.py` | slides 11–15 plus the appendix of questions |
| `fixes.py` | edits applied to the 13 existing school slides, by shape lookup |
| `esports.py` | standalone 14-slide esports deck, company-agnostic, for sending rather than presenting |
| `marwah.py` | standalone 12-slide esports deck for Marwah Sports, aimed at an operations reader |
| `verify.py` | flags text that spills out of its card, crosses the footer rule, or leaves the page |
| `collide.py` | flags text overlapping other text, or running past the margins |

## Checking a build

```sh
../biocore/backend/.venv/Scripts/python.exe verify.py  ../BioCore_x_QuickCampus.pptx
../biocore/backend/.venv/Scripts/python.exe collide.py ../BioCore_x_QuickCampus.pptx
```

Both measure real Segoe UI / Consolas metrics with PIL and re-wrap each
paragraph, because PowerPoint boxes are `SHAPE_TO_FIT_TEXT` — a box grows
downward past its card without any error. Run both against
`../BioCore_for_Schools.pptx` to see them reproduce the known slide-4 overlap;
that is the calibration case.

## House rules, taken from the source deck

- Canvas 20 × 11.25 in. Margin 0.60. Content width 18.80.
- Rules at y=1.12 and y=10.28. Footnotes sit at y≈9.75, never lower.
- Card grids: 3-up at x = 0.60 / 6.98 / 13.37 (w 6.03); 4-up at
  x = 0.60 / 5.39 / 10.17 / 14.96 (w 4.44).
- Headline 42pt Segoe UI Light, accent bar under it, then 16.5pt deck copy.
- Card body copy uses explicit line breaks rather than relying on wrapping —
  that is how the original keeps text inside its card, and why slide 4, the one
  slide that relied on wrapping, was the one that broke.

`ds.py` also carries a vertical spine (`H1`, `BAR1`/`BAR2`, `DECK1`/`DECK2`,
`CARD_T`, `CARD_H`, `FOOT_Y`) and the card-band helpers `trio` / `quad` / `icon`
that the two standalone decks share, so every slide lands its headline, rule,
copy and cards on the same lines. Card bodies run ~0.34 in per line at 13 pt, so
a three-line body needs `CARD_T + 2.10 + 1.02` to clear the card — that is what
sets `CARD_H` at 3.35. `new_deck()` returns a blank presentation already on the
20 × 11.25 canvas.
