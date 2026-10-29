"""Earth-observation helpers used by the generated analysis scripts.

The generated code stays short and readable (search → composite → index → threshold → outputs)
because the plumbing lives here: Sentinel-2 L2A scene search, cloud masking with the scene
classification layer, reprojection onto one analysis grid, compositing and output writing.

Two scene sources are supported and chosen automatically:

* ``planetary-computer`` — the Planetary Computer STAC API (needs ``pystac-client`` and
  ``planetary-computer`` for URL signing);
* ``aws`` — the public ``sentinel-cogs`` bucket of the AWS Registry of Open Data (the archive
  behind Element 84's Earth Search). Its STAC items sit next to the COGs, so the bucket listing
  itself is the catalogue; no API is needed.

All network access goes through :func:`check_url` so the sandbox allow-list is enforced here too.
"""

from __future__ import annotations

import fnmatch
import json
import math
import os
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import numpy as np

BBox = tuple[float, float, float, float]

AWS_BUCKET = "https://sentinel-cogs.s3.us-west-2.amazonaws.com"
AWS_PREFIX = "sentinel-s2-l2a-cogs"
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
JRC_GSW = "https://storage.googleapis.com/global-surface-water/downloads2021"

DEFAULT_ALLOWED = (
    "sentinel-cogs.s3.us-west-2.amazonaws.com",
    "planetarycomputer.microsoft.com",
    "*.blob.core.windows.net",
    "earth-search.aws.element84.com",
    "storage.googleapis.com",
)

# Scene classification (SCL) classes treated as invalid: no data, saturated, cloud shadow,
# cloud medium/high probability, thin cirrus. Snow (11) is kept: it is a real surface.
SCL_INVALID = (0, 1, 3, 8, 9, 10)

# Asset keys differ between catalogues; map common band names to both.
BANDS = {
    "blue": ("blue", "B02"),
    "green": ("green", "B03"),
    "red": ("red", "B04"),
    "nir": ("nir", "B08"),
    "swir16": ("swir16", "B11"),
    "swir22": ("swir22", "B12"),
    "scl": ("scl", "SCL"),
}


class NetworkPolicyError(PermissionError):
    pass


def allowed_hosts() -> tuple[str, ...]:
    env = os.environ.get("GEORAG_ALLOWED_HOSTS")
    return tuple(h.strip() for h in env.split(",") if h.strip()) if env else DEFAULT_ALLOWED


def check_url(url: str) -> str:
    host = urlparse(url).hostname or ""
    if not any(fnmatch.fnmatch(host, pat) for pat in allowed_hosts()):
        raise NetworkPolicyError(f"host not on the analysis allow-list: {host}")
    return url


def _http_get(url: str, timeout: float = 60) -> bytes:
    import httpx

    check_url(url)
    for attempt in range(3):
        try:
            r = httpx.get(url, timeout=timeout, follow_redirects=False)
            r.raise_for_status()
            return r.content
        except httpx.HTTPError:
            if attempt == 2:
                raise
    raise RuntimeError("unreachable")


# ------------------------------------------------------------------------------------- MGRS grid
_LAT_BANDS = "CDEFGHJKLMNPQRSTUVWX"
_COL_SETS = ("ABCDEFGH", "JKLMNPQR", "STUVWXYZ")
_ROW_LETTERS = "ABCDEFGHJKLMNPQRSTUV"


def utm_epsg(lon: float, lat: float) -> int:
    zone = utm_zone(lon, lat)
    return (32600 if lat >= 0 else 32700) + zone


def utm_zone(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    if 56 <= lat < 64 and 3 <= lon < 12:
        zone = 32
    if 72 <= lat < 84:
        for lo, hi, z in ((0, 9, 31), (9, 21, 33), (21, 33, 35), (33, 42, 37)):
            if lo <= lon < hi:
                zone = z
    return min(zone, 60)


def mgrs_tile(lon: float, lat: float, zone: int | None = None) -> str:
    """Return the Sentinel-2 / MGRS 100 km tile id (e.g. ``32SNG``) containing a point.

    ``zone`` forces a UTM zone, which is how a point is located in the neighbouring zone's grid.
    """
    from pyproj import Transformer

    zone = zone or utm_zone(lon, lat)
    band = _LAT_BANDS[min(int((lat + 80) // 8), len(_LAT_BANDS) - 1)]
    epsg = (32600 if lat >= 0 else 32700) + zone
    e, n = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon, lat)
    set_no = zone % 6 or 6
    col = _COL_SETS[(set_no - 1) % 3][int(e // 100_000) - 1]
    row_idx = int(n // 100_000) % 20
    if set_no % 2 == 0:
        row_idx = (row_idx + 5) % 20
    return f"{zone}{band}{col}{_ROW_LETTERS[row_idx]}"


def tiles_for_bbox(bbox: BBox, samples: int = 5) -> list[str]:
    lon0, lat0, lon1, lat1 = bbox
    tiles: dict[str, None] = {}
    for i in range(samples):
        for j in range(samples):
            lon = lon0 + (lon1 - lon0) * i / (samples - 1)
            lat = lat0 + (lat1 - lat0) * j / (samples - 1)
            zone = utm_zone(lon, lat)
            tiles[mgrs_tile(lon, lat)] = None
            # Sentinel-2 does not produce every MGRS square at a zone edge: some areas are only
            # covered by the overlapping tiles of the neighbouring zone, so look there too.
            offset = (lon + 180) % 6
            if offset < 1.0 and zone > 1:
                tiles[mgrs_tile(lon, lat, zone - 1)] = None
            elif offset > 5.0 and zone < 60:
                tiles[mgrs_tile(lon, lat, zone + 1)] = None
    return list(tiles)


# ------------------------------------------------------------------------------------ scenes
@dataclass
class Scene:
    id: str
    datetime: str
    cloud_cover: float
    assets: dict[str, str]
    scale_offset: dict[str, tuple[float, float]]
    geometry: dict
    tile: str = ""
    nodata_pct: float = 0.0
    aoi_valid: float | None = None
    extra: dict = field(default_factory=dict)

    @property
    def day(self) -> str:
        return self.datetime[:10]

    def href(self, band: str) -> str:
        for key in BANDS.get(band, (band,)):
            if key in self.assets:
                return self.assets[key]
        raise KeyError(f"band {band} not in scene {self.id}")

    def scaling(self, band: str) -> tuple[float, float]:
        for key in BANDS.get(band, (band,)):
            if key in self.scale_offset:
                return self.scale_offset[key]
        return (1e-4, 0.0)


def _scene_from_item(item: dict, sign=None) -> Scene:
    props = item["properties"]
    assets, scaling = {}, {}
    for key, a in item["assets"].items():
        if not a.get("href", "").endswith((".tif", ".TIF")) and "image/tiff" not in a.get("type", ""):
            continue
        assets[key] = sign(a["href"]) if sign else a["href"]
        rb = (a.get("raster:bands") or [{}])[0]
        if "scale" in rb or "offset" in rb:
            scaling[key] = (float(rb.get("scale", 1.0)), float(rb.get("offset", 0.0)))
    tile = f"{props.get('mgrs:utm_zone', '')}{props.get('mgrs:latitude_band', '')}{props.get('mgrs:grid_square', '')}"
    if not scaling:
        # Planetary Computer does not publish raster:bands; since processing baseline 04.00
        # (25 January 2022) L2A digital numbers carry a +1000 offset (BOA_ADD_OFFSET).
        baseline = float(props.get("s2:processing_baseline", "0") or 0)
        off = -0.1 if baseline >= 4.0 else 0.0
        scaling = {k: (1e-4, off) for k in assets if k.upper() not in ("SCL", "AOT", "WVP", "VISUAL")}
    return Scene(
        id=item["id"],
        datetime=props["datetime"],
        cloud_cover=float(props.get("eo:cloud_cover", 100.0)),
        assets=assets,
        scale_offset=scaling,
        geometry=item["geometry"],
        tile=tile or props.get("s2:mgrs_tile", ""),
        nodata_pct=float(props.get("s2:nodata_pixel_percentage", 0.0)),
    )


def _month_range(month: str) -> tuple[date, date]:
    y, m = (int(x) for x in month.split("-"))
    start = date(y, m, 1)
    end = date(y + (m == 12), m % 12 + 1, 1)
    return start, end


def _aws_list(prefix: str) -> list[str]:
    url = f"{AWS_BUCKET}/?list-type=2&prefix={prefix}&delimiter=/"
    root = ElementTree.fromstring(_http_get(url))
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    return [p.text for p in root.findall("s3:CommonPrefixes/s3:Prefix", ns) if p.text]


def search_aws(bbox: BBox, month: str, max_cloud: float) -> list[Scene]:
    from shapely.geometry import box, shape

    aoi = box(*bbox)
    y, m = month.split("-")
    prefixes = []
    for tile in tiles_for_bbox(bbox):
        zone, band, sq = tile[:-3], tile[-3], tile[-2:]
        prefixes.extend(_aws_list(f"{AWS_PREFIX}/{zone}/{band}/{sq}/{int(y)}/{int(m)}/"))

    def fetch(prefix: str) -> dict | None:
        name = prefix.rstrip("/").rsplit("/", 1)[-1]
        try:
            return json.loads(_http_get(f"{AWS_BUCKET}/{prefix}{name}.json"))
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        items = [it for it in pool.map(fetch, prefixes) if it]
    scenes = []
    for it in items:
        s = _scene_from_item(it)
        if s.cloud_cover <= max_cloud and shape(s.geometry).intersects(aoi):
            s.extra["coverage"] = shape(s.geometry).intersection(aoi).area / aoi.area
            scenes.append(s)
    return _dedupe(scenes)


def search_planetary_computer(bbox: BBox, month: str, max_cloud: float) -> list[Scene]:
    import planetary_computer
    import pystac_client
    from shapely.geometry import box, shape

    check_url(PC_STAC)
    start, end = _month_range(month)
    catalog = pystac_client.Client.open(PC_STAC, modifier=planetary_computer.sign_inplace)
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{start.isoformat()}/{end.isoformat()}",
        query={"eo:cloud_cover": {"lte": max_cloud}},
    )
    aoi = box(*bbox)
    scenes = []
    for item in search.items_as_dicts():
        s = _scene_from_item(item)
        s.extra["coverage"] = shape(s.geometry).intersection(aoi).area / aoi.area
        scenes.append(s)
    return _dedupe(scenes)


def _dedupe(scenes: list[Scene]) -> list[Scene]:
    """One scene per (tile, day): reprocessed duplicates keep the one with least missing data."""
    best: dict[tuple[str, str], Scene] = {}
    for s in scenes:
        key = (s.tile, s.day)
        if key not in best or s.nodata_pct < best[key].nodata_pct:
            best[key] = s
    return sorted(best.values(), key=lambda s: (s.cloud_cover, s.nodata_pct))


def search_scenes(
    bbox: BBox, month: str, max_cloud: float = 30.0, source: str = "auto"
) -> tuple[list[Scene], str]:
    if source in ("auto", "planetary-computer"):
        try:
            return search_planetary_computer(bbox, month, max_cloud), "planetary-computer"
        except Exception:
            if source == "planetary-computer":
                raise
    return search_aws(bbox, month, max_cloud), "aws"


# -------------------------------------------------------------------------------------- grid
@dataclass
class Grid:
    crs: str
    transform: object  # affine.Affine
    width: int
    height: int
    bbox: BBox
    resolution: float

    @property
    def pixel_area_m2(self) -> float:
        return self.resolution * self.resolution


def analysis_grid(bbox: BBox, resolution: float = 20.0) -> Grid:
    from pyproj import Transformer
    from rasterio.transform import from_origin

    lon_c, lat_c = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    epsg = utm_epsg(lon_c, lat_c)
    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = [], []
    for lon in np.linspace(bbox[0], bbox[2], 11):
        for lat in np.linspace(bbox[1], bbox[3], 11):
            x, y = tr.transform(lon, lat)
            xs.append(x)
            ys.append(y)
    x0 = math.floor(min(xs) / resolution) * resolution
    y1 = math.ceil(max(ys) / resolution) * resolution
    width = math.ceil((max(xs) - x0) / resolution)
    height = math.ceil((y1 - min(ys)) / resolution)
    return Grid(f"EPSG:{epsg}", from_origin(x0, y1, resolution, resolution), width, height, bbox, resolution)


def _gdal_env():
    import rasterio

    opts = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff",
        "GDAL_HTTP_MULTIRANGE": "YES",
        "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
        "GDAL_HTTP_MAX_RETRY": "4",
        "GDAL_HTTP_RETRY_DELAY": "1",
        "VSI_CACHE": "TRUE",
    }
    ca = (
        os.environ.get("SSL_CERT_FILE")
        or os.environ.get("REQUESTS_CA_BUNDLE")
        or os.environ.get("CURL_CA_BUNDLE")
    )
    if ca:
        opts["GDAL_CURL_CA_BUNDLE"] = ca
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        opts["GDAL_HTTP_PROXY"] = proxy
    return rasterio.Env(**opts)


def read_band(href: str, grid: Grid, resampling: str = "bilinear", dtype: str = "float32") -> np.ndarray:
    """Read one COG onto the analysis grid (only the needed blocks are fetched over HTTP)."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT

    check_url(href)
    with (
        _gdal_env(),
        rasterio.open(href) as src,
        WarpedVRT(
            src,
            crs=grid.crs,
            transform=grid.transform,
            width=grid.width,
            height=grid.height,
            resampling=getattr(Resampling, resampling),
            src_nodata=src.nodata if src.nodata is not None else 0,
            nodata=0,
        ) as vrt,
    ):
        return vrt.read(1).astype(dtype)


def read_scene(scene: Scene, grid: Grid, bands: Iterable[str]) -> dict[str, np.ndarray]:
    """Reflectance bands (float, NaN where invalid) plus the validity mask for one scene."""
    scl = read_band(scene.href("scl"), grid, resampling="nearest", dtype="uint8")
    valid = ~np.isin(scl, SCL_INVALID)
    out: dict[str, np.ndarray] = {"valid": valid, "scl": scl}
    for b in bands:
        dn = read_band(scene.href(b), grid)
        scale, offset = scene.scaling(b)
        if offset < 0:
            # Catalogue flags about the +1000 BOA offset are not reliable across reprocessings.
            # The data are: with the offset still in place almost no valid pixel is below 1000.
            ok = dn[(dn > 0) & valid]
            if ok.size and np.percentile(ok, 1) < -offset / scale * 0.9:
                offset = 0.0
        refl = dn * scale + offset
        refl[(dn == 0) | ~valid] = np.nan
        out[b] = refl
    return out


def normalized_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        nd = (a - b) / (a + b)
    return np.clip(nd, -1, 1)


INDEX_BANDS = {"MNDWI": ("green", "swir16"), "NDWI": ("green", "nir"), "NDVI": ("nir", "red")}


@dataclass
class Composite:
    month: str
    index_name: str
    index: np.ndarray  # median over valid observations
    rgb: np.ndarray  # median true colour, reflectance 0..1
    valid_count: np.ndarray
    scenes: list[Scene]
    grid: Grid
    source: str

    @property
    def coverage(self) -> float:
        return float((self.valid_count > 0).mean())


def monthly_composite(
    bbox: BBox,
    month: str,
    index: str = "MNDWI",
    max_cloud: float = 30.0,
    max_scenes: int = 4,
    resolution: float = 20.0,
    min_valid: float = 0.5,
    source: str = "auto",
    log=print,
) -> Composite:
    """Median composite of a normalized-difference index over the clearest scenes of a month."""
    grid = analysis_grid(bbox, resolution)
    scenes, used_source = search_scenes(bbox, month, max_cloud, source)
    if not scenes:
        raise LookupError(f"no Sentinel-2 L2A scenes for {month} with cloud cover <= {max_cloud}%")
    log(
        f"{month}: {len(scenes)} candidate scenes from {used_source}; grid {grid.width}x{grid.height} @ {resolution} m ({grid.crs})"
    )
    a_band, b_band = INDEX_BANDS[index]
    stack: list[np.ndarray] = []
    rgbs: list[np.ndarray] = []
    used: list[Scene] = []
    counts = np.zeros((grid.height, grid.width), np.int16)
    for s in scenes:
        if len(used) >= max_scenes:
            break
        try:
            data = read_scene(s, grid, [a_band, b_band, "red", "green", "blue"])
        except Exception as exc:  # a single unreadable scene should not end the analysis
            log(f"  skip {s.id}: {exc}")
            continue
        valid_frac = float(np.isfinite(data[a_band]).mean())
        s.aoi_valid = round(valid_frac, 3)
        if valid_frac < min_valid:
            log(f"  skip {s.id}: only {valid_frac:.0%} clear pixels over the area")
            continue
        log(f"  use  {s.id} ({s.day}, scene cloud {s.cloud_cover:.0f}%, clear over area {valid_frac:.0%})")
        stack.append(normalized_difference(data[a_band], data[b_band]))
        rgbs.append(np.stack([data["red"], data["green"], data["blue"]]))
        counts += np.isfinite(stack[-1]).astype(np.int16)
        used.append(s)
    if not used:
        raise LookupError(f"no scene in {month} has at least {min_valid:.0%} clear pixels over the area")
    with np.errstate(all="ignore"):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            idx = np.nanmedian(np.stack(stack), axis=0)
            rgb = np.nanmedian(np.stack(rgbs), axis=0)
    return Composite(
        month, index, idx.astype(np.float32), rgb.astype(np.float32), counts, used, grid, used_source
    )


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    v = values[np.isfinite(values)]
    if v.size == 0:
        return 0.0
    hist, edges = np.histogram(v, bins=bins, range=(-1, 1))
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centers) / np.maximum(w0, 1)
    m1 = (np.sum(hist * centers) - np.cumsum(hist * centers)) / np.maximum(w1, 1)
    between = w0 * w1 * (m0 - m1) ** 2
    return float(centers[int(np.argmax(between))])


def water_stats(comp: Composite, threshold: float = 0.0) -> tuple[np.ndarray, dict]:
    mask = comp.index > threshold
    observed = np.isfinite(comp.index)
    km2 = mask.sum() * comp.grid.pixel_area_m2 / 1e6
    return mask, {
        "month": comp.month,
        "index": comp.index_name,
        "threshold": round(float(threshold), 3),
        "water_km2": round(float(km2), 3),
        "observed_fraction": round(float(observed.mean()), 4),
        "scenes": [s.id for s in comp.scenes],
        "scene_dates": [s.day for s in comp.scenes],
        "source": comp.source,
        "otsu_threshold": round(otsu_threshold(comp.index), 3),
    }


def ndvi_stats(comp: Composite) -> dict:
    v = comp.index[np.isfinite(comp.index)]
    classes = {
        "bare_or_water(<0.2)": (v < 0.2).mean(),
        "sparse(0.2-0.5)": ((v >= 0.2) & (v < 0.5)).mean(),
        "dense(>=0.5)": (v >= 0.5).mean(),
    }
    return {
        "month": comp.month,
        "index": "NDVI",
        "mean": round(float(v.mean()), 4) if v.size else None,
        "median": round(float(np.median(v)), 4) if v.size else None,
        "p10": round(float(np.percentile(v, 10)), 4) if v.size else None,
        "p90": round(float(np.percentile(v, 90)), 4) if v.size else None,
        "class_fractions": {k: round(float(x), 4) for k, x in classes.items()},
        "observed_fraction": round(float(np.isfinite(comp.index).mean()), 4),
        "scenes": [s.id for s in comp.scenes],
        "scene_dates": [s.day for s in comp.scenes],
        "source": comp.source,
    }


# ------------------------------------------------------------------------------------- outputs
def write_geotiff(path: Path | str, array: np.ndarray, grid: Grid, nodata: float | None = None) -> Path:
    import rasterio

    path = Path(path)
    arr = array.astype("float32") if array.dtype.kind == "f" else array.astype("uint8")
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=grid.width,
        height=grid.height,
        count=1,
        dtype=arr.dtype,
        crs=grid.crs,
        transform=grid.transform,
        nodata=nodata,
        compress="deflate",
        tiled=True,
    ) as dst:
        dst.write(arr, 1)
    return path


def _to_lonlat(array: np.ndarray, grid: Grid, resampling: str = "nearest") -> tuple[np.ndarray, BBox]:
    """Reproject a grid array to EPSG:4326 for web map overlays."""
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds
    from rasterio.warp import reproject

    lon0, lat0, lon1, lat1 = grid.bbox
    h = grid.height
    w = max(1, round(h * (lon1 - lon0) * math.cos(math.radians((lat0 + lat1) / 2)) / (lat1 - lat0)))
    dst = np.full((array.shape[0], h, w) if array.ndim == 3 else (h, w), np.nan, dtype=np.float32)
    reproject(
        array.astype(np.float32),
        dst,
        src_transform=grid.transform,
        src_crs=grid.crs,
        dst_transform=from_bounds(lon0, lat0, lon1, lat1, w, h),
        dst_crs="EPSG:4326",
        resampling=getattr(Resampling, resampling),
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )
    return dst, grid.bbox


def _rgb_uint8(rgb: np.ndarray, gain: float = 3.2) -> np.ndarray:
    img = np.nan_to_num(np.moveaxis(rgb, 0, -1) * gain, nan=0.0)
    img = np.clip(img ** (1 / 1.25), 0, 1)
    return (img * 255).astype(np.uint8)


def save_overlay(path: Path | str, rgba: np.ndarray) -> Path:
    import matplotlib.image as mpimg

    path = Path(path)
    mpimg.imsave(path, rgba)
    return path


# ColorBrewer colours shared by the web overlays and the static figures.
WATER = "#2b8cbe"
WATER_STABLE = "#9ecae1"
GAIN = "#1a9641"
LOSS = "#d7191c"
LAND = "#f0efe9"
INK = "#1c1c1a"


def _hex_rgba(color: str, alpha: int) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), alpha)


def web_layers(
    out_dir: Path | str,
    comp: Composite,
    mask: np.ndarray | None = None,
    change: np.ndarray | None = None,
    prefix: str = "",
) -> dict:
    """Write EPSG:4326 PNG overlays (true colour, index, water or change) for the map panel."""
    out = Path(out_dir)
    layers = {}
    rgb, bounds = _to_lonlat(comp.rgb, comp.grid, "bilinear")
    rgba = np.dstack([_rgb_uint8(rgb), np.where(np.isfinite(rgb[0]), 255, 0).astype(np.uint8)])
    layers["truecolor"] = save_overlay(out / f"{prefix}truecolor.png", rgba).name
    if mask is not None:
        m, _ = _to_lonlat(mask.astype(np.float32), comp.grid)
        rgba = np.zeros((*m.shape, 4), np.uint8)
        rgba[m > 0.5] = _hex_rgba(WATER, 215)
        layers["water"] = save_overlay(out / f"{prefix}water.png", rgba).name
    if comp.index_name == "NDVI":
        import matplotlib

        v, _ = _to_lonlat(comp.index, comp.grid, "bilinear")
        cmap = matplotlib.colormaps["RdYlGn"]
        rgba = (cmap(np.clip((np.nan_to_num(v, nan=-1) + 0.2) / 1.1, 0, 1)) * 255).astype(np.uint8)
        rgba[..., 3] = np.where(np.isfinite(v), 220, 0)
        layers["ndvi"] = save_overlay(out / f"{prefix}ndvi.png", rgba).name
    if change is not None:
        c, _ = _to_lonlat(change.astype(np.float32), comp.grid)
        rgba = np.zeros((*c.shape, 4), np.uint8)
        rgba[c == 1] = _hex_rgba(GAIN, 235)
        rgba[c == -1] = _hex_rgba(LOSS, 235)
        rgba[c == 2] = _hex_rgba(WATER_STABLE, 170)
        layers["change"] = save_overlay(out / "change.png", rgba).name
    return {"bounds": list(bounds), "layers": layers}


def _figure_style(ax, label: str, title: str) -> None:
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=6)
    ax.text(
        0.0,
        1.0,
        label,
        transform=ax.transAxes,
        fontsize=11,
        fontweight="bold",
        va="bottom",
        ha="right",
        color=INK,
    )
    ax.tick_params(colors="#4a4843", labelsize=8, length=3)
    ax.set_xlabel("km", color="#4a4843", fontsize=9)
    for sp in ax.spines.values():
        sp.set_color("#4a4843")
        sp.set_linewidth(0.8)


def figure_water_change(
    path: Path | str,
    a: Composite,
    b: Composite,
    mask_a: np.ndarray,
    mask_b: np.ndarray,
    title: str,
    stats: dict,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), facecolor="white")
    extent = (0, a.grid.width * a.grid.resolution / 1000, 0, a.grid.height * a.grid.resolution / 1000)
    for ax, comp, mask, label in ((axes[0], a, mask_a, "(a)"), (axes[1], b, mask_b, "(b)")):
        ax.imshow(_rgb_uint8(comp.rgb), extent=extent)
        ov = np.ma.masked_where(~mask, mask)
        ax.imshow(ov, cmap=ListedColormap([WATER]), alpha=0.6, extent=extent, interpolation="nearest")
        km2 = mask.sum() * comp.grid.pixel_area_m2 / 1e6
        _figure_style(ax, label, f"  {comp.month}: open water {km2:.1f} km²")
    change = np.zeros(mask_a.shape, np.int8)
    change[mask_a & mask_b] = 2
    change[~mask_a & mask_b] = 1
    change[mask_a & ~mask_b] = -1
    cmap = ListedColormap([LOSS, LAND, GAIN, WATER_STABLE])
    axes[2].imshow(change, cmap=cmap, vmin=-1.5, vmax=2.5, extent=extent, interpolation="nearest")
    _figure_style(axes[2], "(c)", f"  Change: {stats['change_km2']:+.1f} km² ({stats['change_pct']:+.0f} %)")
    axes[2].legend(
        handles=[
            Patch(facecolor=WATER_STABLE, edgecolor="#4a4843", linewidth=0.5, label="water in both"),
            Patch(facecolor=GAIN, edgecolor="#4a4843", linewidth=0.5, label="became water"),
            Patch(facecolor=LOSS, edgecolor="#4a4843", linewidth=0.5, label="dried out"),
        ],
        loc="lower left",
        fontsize=9,
        frameon=True,
        fancybox=False,
        edgecolor="#4a4843",
        framealpha=1,
    )
    fig.suptitle(title, x=0.01, ha="left", fontsize=13, color=INK, y=0.99)
    fig.text(
        0.01,
        0.01,
        "Data: Copernicus Sentinel-2 L2A. Monthly median of clear scenes, SCL cloud mask; water where MNDWI > threshold.",
        color="#6f6c65",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(path, dpi=130, facecolor="white")
    plt.close(fig)
    return Path(path)


def figure_index(path: Path | str, comp: Composite, title: str, mask: np.ndarray | None = None) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), facecolor="white")
    extent = (
        0,
        comp.grid.width * comp.grid.resolution / 1000,
        0,
        comp.grid.height * comp.grid.resolution / 1000,
    )
    axes[0].imshow(_rgb_uint8(comp.rgb), extent=extent)
    _figure_style(axes[0], "(a)", f"  True colour, {comp.month}")
    cmap = "RdYlGn" if comp.index_name == "NDVI" else "BrBG"
    im = axes[1].imshow(
        comp.index,
        cmap=cmap,
        vmin=-0.4 if comp.index_name == "NDVI" else -0.8,
        vmax=0.9 if comp.index_name == "NDVI" else 0.8,
        extent=extent,
    )
    if mask is not None:
        axes[1].contour(mask, levels=[0.5], colors=INK, linewidths=0.6, extent=extent, origin="upper")
    _figure_style(axes[1], "(b)", f"  {comp.index_name}")
    cb = fig.colorbar(im, ax=axes[1], fraction=0.046, pad=0.03)
    cb.ax.tick_params(colors="#4a4843", labelsize=8)
    cb.outline.set_edgecolor("#4a4843")
    fig.suptitle(title, x=0.01, ha="left", fontsize=13, color=INK)
    fig.text(
        0.01,
        0.01,
        "Data: Copernicus Sentinel-2 L2A, monthly median of clear scenes, SCL cloud mask.",
        color="#6f6c65",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(path, dpi=130, facecolor="white")
    plt.close(fig)
    return Path(path)


# ------------------------------------------------------------------------------- reference data
def jrc_occurrence(bbox: BBox, grid: Grid | None = None) -> tuple[np.ndarray, Grid]:
    """JRC Global Surface Water occurrence (0–100 %) on the analysis grid (nearest neighbour)."""
    lon_c, lat_c = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    lon_tile = int(math.floor(lon_c / 10) * 10)
    lat_tile = int(math.ceil(lat_c / 10) * 10)
    lon_s = f"{abs(lon_tile)}{'E' if lon_tile >= 0 else 'W'}"
    lat_s = f"{abs(lat_tile)}{'N' if lat_tile >= 0 else 'S'}"
    url = f"{JRC_GSW}/occurrence/occurrence_{lon_s}_{lat_s}v1_4_2021.tif"
    grid = grid or analysis_grid(bbox, 20.0)
    occ = read_band(url, grid, resampling="nearest", dtype="float32")
    return occ, grid
