import pytest

from georag.agent.analyze import deterministic_repair, heuristic_plan, parse_periods, render, validate_plan
from georag.geo import gazetteer
from georag.geo.eo import mgrs_tile, otsu_threshold, tiles_for_bbox, utm_epsg
from georag.sandbox import static_check
from georag.schemas import AnalysisPlan


@pytest.mark.parametrize(
    "lon,lat,tile",
    [
        (9.66, 37.16, "32SNG"),
        (9.80, 36.50, "32SNF"),
        (4.36, 52.01, "31UET"),
        (-122.42, 37.77, "10SEG"),
        (151.21, -33.87, "56HLH"),
    ],
)
def test_mgrs_tiles(lon, lat, tile):
    assert mgrs_tile(lon, lat) == tile


def test_utm_epsg_and_tile_cover():
    assert utm_epsg(9.66, 37.16) == 32632
    assert utm_epsg(151.2, -33.9) == 32756
    assert "32SNG" in tiles_for_bbox((9.55, 37.10, 9.775, 37.215))


def test_parse_periods():
    assert parse_periods("February 2020 vs February 2025") == ["2020-02", "2025-02"]
    assert parse_periods("Feb 2020 vs 2025") == ["2020-02", "2025-02"]
    assert parse_periods("for 2024-07") == ["2024-07"]
    assert parse_periods("a summer month in 2024") == ["2024-07"]


def test_heuristic_plan_ichkeul():
    p = heuristic_plan("Map MNDWI water extent at Ichkeul for February 2020 vs February 2025.")
    assert p.task == "water_change" and p.index == "MNDWI"
    assert p.periods == ["2020-02", "2025-02"]
    assert p.bbox == gazetteer.PLACES["ichkeul"]["bbox"]


def test_heuristic_plan_bbox_and_name():
    p = heuristic_plan(
        "Map the open-water extent of Lake Bled (bbox 14.07, 46.35, 14.11, 46.37) in August 2024."
    )
    assert p.task == "water_extent" and p.place == "Lake Bled" and p.bbox == (14.07, 46.35, 14.11, 46.37)


def test_validate_plan_never_trusts_model_geography():
    fallback = heuristic_plan("NDVI around Bizerte for July 2024")
    llm_plan = AnalysisPlan(
        task="ndvi",
        place="Paris",
        bbox=(2.2, 48.8, 2.4, 48.9),
        periods=["2019-01"],
        index="MNDWI",
        max_cloud=500,
        max_scenes=50,
    )
    v = validate_plan(llm_plan, fallback)
    assert v.bbox == fallback.bbox and v.periods == ["2024-07"] and v.index == "NDVI"
    assert v.max_cloud <= 80 and v.max_scenes <= 6


def test_repair_widens_cloud_then_moves_month():
    p = heuristic_plan("Map water at Ichkeul in February 2025")
    p1 = deterministic_repair(p, "LookupError: no Sentinel-2 L2A scenes for 2025-02", 1)
    assert p1.max_cloud > p.max_cloud
    p2 = deterministic_repair(
        p1.model_copy(update={"max_cloud": 70}), "no scene in 2025-02 has at least 50% clear pixels", 2
    )
    assert p2.periods != p1.periods


@pytest.mark.parametrize(
    "q",
    [
        "Map MNDWI water extent at Ichkeul for February 2020 vs February 2025.",
        "Compute NDVI around Bizerte for July 2024.",
        "Map water at Sidi Salem in March 2023",
    ],
)
def test_templates_render_valid_code(q):
    code = render(heuristic_plan(q), "title")
    compile(code, "x.py", "exec")
    static_check(code)


def test_otsu_bimodal():
    import numpy as np

    v = np.concatenate(
        [np.random.default_rng(0).normal(-0.4, 0.05, 1000), np.random.default_rng(1).normal(0.5, 0.05, 1000)]
    )
    assert -0.35 < otsu_threshold(v) < 0.45


def test_zone_edge_includes_neighbouring_zone():
    # Lake Annecy sits just east of 6°E; Sentinel-2 covers it from zone 31 (31TGL), not 32TKR.
    tiles = tiles_for_bbox((6.11, 45.78, 6.25, 45.92))
    assert "31TGL" in tiles and "32TKR" in tiles
