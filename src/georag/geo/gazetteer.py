"""A small built-in gazetteer of study areas (bounding boxes in WGS 84 lon/lat).

The analysis planner resolves place names here first; a user can always pass an explicit
bounding box instead. Boxes are drawn around the feature of interest with a margin and, for
lakes, kept clear of the sea so that a water mask measures the lake alone.
"""

from __future__ import annotations

import re
import unicodedata

BBox = tuple[float, float, float, float]

PLACES: dict[str, dict] = {
    "ichkeul": {
        "name": "Lake Ichkeul, Tunisia",
        "bbox": (9.55, 37.10, 9.775, 37.215),
        "aliases": ["lake ichkeul", "ichkeul national park", "garaet ichkeul"],
    },
    "bizerte": {
        "name": "Bizerte, Tunisia",
        "bbox": (9.72, 37.12, 9.98, 37.32),
        "aliases": ["bizerta", "lake bizerte", "bizerte lagoon"],
    },
    "tunis": {
        "name": "Tunis, Tunisia",
        "bbox": (10.05, 36.72, 10.35, 36.92),
        "aliases": ["lake of tunis", "lac de tunis"],
    },
    "sidi_salem": {
        "name": "Sidi Salem reservoir, Tunisia",
        "bbox": (9.28, 36.52, 9.48, 36.64),
        "aliases": ["sidi salem", "sidi salem dam", "barrage sidi salem"],
    },
    "delft": {"name": "Delft, Netherlands", "bbox": (4.32, 51.97, 4.42, 52.03), "aliases": []},
    "rotterdam": {"name": "Rotterdam, Netherlands", "bbox": (4.38, 51.87, 4.58, 51.97), "aliases": []},
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", text).strip()


def resolve(place: str) -> tuple[str, BBox] | None:
    q = _norm(place)
    for key, p in PLACES.items():
        names = [key.replace("_", " "), _norm(p["name"]), *(_norm(a) for a in p["aliases"])]
        if any(n == q or re.search(rf"\b{re.escape(n)}\b", q) for n in names):
            return p["name"], tuple(p["bbox"])
    return None


def find_in_text(text: str) -> tuple[str, BBox] | None:
    """Find the first gazetteer place mentioned anywhere in free text."""
    q = _norm(text)
    best: tuple[int, str, BBox] | None = None
    for key, p in PLACES.items():
        for n in [key.replace("_", " "), *(_norm(a) for a in p["aliases"]), _norm(p["name"].split(",")[0])]:
            m = re.search(rf"\b{re.escape(n)}\b", q)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), p["name"], tuple(p["bbox"]))
    return (best[1], best[2]) if best else None


def parse_bbox(text: str) -> BBox | None:
    """Accept 'lon_min, lat_min, lon_max, lat_max' anywhere in a string."""
    m = re.search(
        r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", text
    )
    if not m:
        return None
    a, b, c, d = (float(x) for x in m.groups())
    if not (-180 <= a < c <= 180 and -90 <= b < d <= 90):
        return None
    return (a, b, c, d)
