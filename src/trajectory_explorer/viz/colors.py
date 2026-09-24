"""Shared color palettes for the trajectory-visualization app.

Palette source: the `dataviz` skill's documented reference palette
(8 fixed-order, colorblind-validated categorical hues + a fixed status
scale). Values are taken verbatim from that palette's light-mode column
(`references/palette.md`) so the same hex codes are used consistently in
both the pydeck map layers and the Plotly charts.

Known, deliberate deviation from the skill's guidance
------------------------------------------------------
The skill's categorical palette validates all-pairs CVD separation
(the check that applies to scatter/map/bubble forms, where any two marks
can sit side by side) for only its **first three** slots; beyond three,
its guidance is to fold categories into "Other" or facet rather than add
more hues. This app has a fixed, small domain of exactly six object
classes (car/truck/van/bicycle/motorbike/pedestrian) that all need to be
simultaneously distinguishable as dots on one map, so folding/faceting
isn't an option.

We brute-forced all 28 six-of-eight subsets of the documented palette
through the skill's own validator (`validate_palette.py ... --pairs all`)
to find the least-bad combination. No 6-hue subset clears the all-pairs
CVD floor (confirming the skill's stated 3-hue cap is a hard limit, not a
missed ordering) -- the best subset (dropping magenta and violet, which
collide most with the others) gets worst-case all-pairs ΔE to ~2.7-3.2
(protan/deutan) and ~7.1 (normal vision), vs. the target of 8 / floor of 6
and normal-vision floor of 15.

Given that, this palette ships with **mandatory secondary encoding** as
required by the skill whenever CVD separation can't clear the floor on
its own:
  - a persistent, text-labeled legend (never color-only identity) wherever
    `CLASS_COLORS` is used,
  - marker size independently encodes rough object size (see
    `viz/scene_map.py`, sized off `dimension.length`/`dimension.width`),
    which is itself a decent proxy for class (pedestrians/bicycles are
    small, trucks are large) and reduces reliance on hue alone,
  - hover tooltips that always spell out the class name.
If this app grows to needing more simultaneously-visible categories,
prefer faceting (small multiples) or an "Other" bucket over adding hues.
"""

# Categorical hues, in the skill's fixed slot order (only the 6 slots that
# validated best together under --pairs all are used; magenta and violet
# are dropped -- see module docstring):
#   slot 1 blue, slot 2 orange, slot 3 aqua, slot 4 yellow, slot 6 green,
#   slot 8 red.
CLASS_COLORS_HEX: dict[str, str] = {
    "car": "#2a78d6",
    "truck": "#eb6834",
    "van": "#1baf7a",
    "bicycle": "#eda100",
    "motorbike": "#008300",
    "pedestrian": "#e34948",
}


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


CLASS_COLORS: dict[str, tuple[int, int, int]] = {
    cls: _hex_to_rgb(hexval) for cls, hexval in CLASS_COLORS_HEX.items()
}

# Fixed order for legends / consistent stacking (matches the assignment above).
CLASS_ORDER: list[str] = ["car", "truck", "van", "bicycle", "motorbike", "pedestrian"]

# Risk scale (low/medium/high), for later TTC/DRAC color-coding during
# playback. Status colors are a separate, fixed scale in the skill's
# palette (never themed, always paired with icon + label, deliberately
# distinct from the categorical slots above so a risk color never gets
# mistaken for an object-class color). We take the "good"/"warning"/
# "critical" steps of that 4-step status scale (skipping "serious", which
# sits between warning and critical) -- these are mode-invariant hexes in
# the documented palette (same value used against both light and dark
# surfaces).
RISK_COLORS_HEX: dict[str, str] = {
    "low": "#0ca30c",
    "medium": "#fab219",
    "high": "#d03b3b",
}

RISK_COLORS: dict[str, tuple[int, int, int]] = {
    level: _hex_to_rgb(hexval) for level, hexval in RISK_COLORS_HEX.items()
}

RISK_ORDER: list[str] = ["low", "medium", "high"]
