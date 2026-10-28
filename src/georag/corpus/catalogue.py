"""Dataset catalogue: what open Earth-observation data exists and how to reach it.

Two sources are supported:

* the Planetary Computer STAC API (``/collections``) — about 130 collections with titles,
  descriptions, licences and band lists;
* the AWS Registry of Open Data, whose dataset descriptions live as YAML files on GitHub.

Whichever is reachable is used; both produce the same :class:`Document` records with
``domain='catalogue'``, so Design mode can cite a dataset like any paper.
"""

from __future__ import annotations

import re

import httpx
import yaml

from georag.schemas import Document

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
AWS_REGISTRY = "https://raw.githubusercontent.com/awslabs/open-data-registry/main/datasets"
AWS_DATASETS = (
    "sentinel-2-l2a-cogs",
    "sentinel-2",
    "sentinel-1",
    "sentinel-1-rtc-indigo",
    "sentinel-3",
    "usgs-landsat",
    "nasa-hls",
    "modis-astraea",
    "naip",
    "usgs-lidar",
    "nasa-gedi",
    "copernicus-dem",
    "esa-worldcover",
    "esa-worldcover-vito",
    "io-lulc",
    "jaxa-alos-palsar2-scansar",
    "overture",
    "terrafusion",
)

# Datasets that are not in either registry but matter for the use cases (validation references).
EXTRA_DATASETS: tuple[dict, ...] = (
    {
        "id": "jrc-global-surface-water",
        "title": "JRC Global Surface Water (v1.4, 1984–2021)",
        "description": (
            "Maps of the location and temporal distribution of surface water from 1984 to 2021 at 30 m, "
            "derived from the full Landsat 5, 7 and 8 archive by the European Commission's Joint Research "
            "Centre. Layers: occurrence (percentage of valid observations that were water), occurrence change, "
            "seasonality (months per year with water), recurrence, transitions and maximum water extent. "
            "Tiles of 10 x 10 degrees are distributed as GeoTIFF from Google Cloud Storage. Commonly used as a "
            "reference to validate lake, reservoir and wetland water masks derived from Sentinel-2 MNDWI."
        ),
        "license": "CC-BY-4.0 (Copernicus Programme data policy)",
        "url": "https://global-surface-water.appspot.com/download",
        "access": "https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/",
    },
    {
        "id": "ahn",
        "title": "AHN — Actueel Hoogtebestand Nederland",
        "description": (
            "National airborne LiDAR of the Netherlands. AHN4 (2020–2022) has 10–14 points per m2, classified "
            "into ground, building, water, bridges and unclassified; AHN5 (2023–2025) and AHN6 densify coverage. "
            "Distributed as LAZ tiles and 0.5 m DSM/DTM rasters through PDOK under CC0. Used for 3D building "
            "reconstruction (3DBAG), rooftop solar potential, flood modelling and tree mapping."
        ),
        "license": "CC0-1.0",
        "url": "https://www.ahn.nl",
        "access": "https://www.ahn.nl/ahn-viewer (download tiles through PDOK)",
    },
    {
        "id": "3dbag",
        "title": "3DBAG — 3D building models of the Netherlands",
        "description": (
            "Open LoD1.2, LoD1.3 and LoD2.2 models of all ~10 million buildings in the Netherlands, reconstructed "
            "automatically from BAG footprints and AHN LiDAR with the roofer/geoflow pipeline of TU Delft's 3D "
            "geoinformation group. Available as CityJSON, OBJ, GeoPackage and 3D Tiles; includes roof plane "
            "attributes (slope, azimuth) used in solar potential studies."
        ),
        "license": "CC-BY-4.0",
        "url": "https://3dbag.nl",
        "access": "https://3dbag.nl/en/download",
    },
)


def _clean(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text or "")
    return re.sub(r"\s+", " ", text).strip()


def from_planetary_computer(client: httpx.Client) -> list[Document]:
    resp = client.get(f"{PC_STAC}/collections")
    resp.raise_for_status()
    docs = []
    for c in resp.json().get("collections", []):
        bands = []
        for item_asset in (c.get("item_assets") or {}).values():
            for b in item_asset.get("eo:bands", []) or []:
                if b.get("name"):
                    bands.append(f"{b['name']} ({b.get('common_name', '')})".replace(" ()", ""))
        interval = (c.get("extent", {}).get("temporal", {}).get("interval") or [[None, None]])[0]
        text = _clean(c.get("description", ""))
        text += f"\nTemporal extent: {interval[0]} to {interval[1] or 'present'}."
        if bands:
            text += f"\nBands: {', '.join(dict.fromkeys(bands))}."
        if c.get("keywords"):
            text += f"\nKeywords: {', '.join(c['keywords'])}."
        docs.append(
            Document(
                doc_id=f"catalogue:pc:{c['id']}",
                source="catalogue",
                title=f"Dataset: {c.get('title', c['id'])}",
                text=text,
                domain="catalogue",
                url=f"https://planetarycomputer.microsoft.com/dataset/{c['id']}",
                licence=c.get("license"),
                authors=["Microsoft Planetary Computer"],
            )
        )
    return docs


def from_aws_registry(client: httpx.Client) -> list[Document]:
    docs = []
    for name in AWS_DATASETS:
        resp = client.get(f"{AWS_REGISTRY}/{name}.yaml")
        if resp.status_code != 200:
            continue
        meta = yaml.safe_load(resp.text)
        resources = meta.get("Resources") or []
        access = [f"{r.get('Description', '').strip()} — {r.get('ARN', '')}" for r in resources[:3]]
        text = _clean(meta.get("Description", ""))
        if meta.get("UpdateFrequency"):
            text += f"\nUpdate frequency: {_clean(meta['UpdateFrequency'])}."
        if meta.get("Tags"):
            text += f"\nTags: {', '.join(meta['Tags'])}."
        if access:
            text += "\nAccess: " + " | ".join(access)
        docs.append(
            Document(
                doc_id=f"catalogue:aws:{name}",
                source="catalogue",
                title=f"Dataset: {meta.get('Name', name)}",
                text=text,
                domain="catalogue",
                url=f"https://registry.opendata.aws/{name}/",
                licence=_clean(meta.get("License", ""))[:200] or None,
                authors=[_clean(meta.get("ManagedBy", "")) or "AWS Open Data"],
            )
        )
    return docs


def extra_datasets() -> list[Document]:
    return [
        Document(
            doc_id=f"catalogue:extra:{d['id']}",
            source="catalogue",
            title=f"Dataset: {d['title']}",
            text=f"{d['description']}\nAccess: {d['access']}",
            domain="catalogue",
            url=d["url"],
            licence=d["license"],
            authors=[],
        )
        for d in EXTRA_DATASETS
    ]


def fetch_catalogue(client: httpx.Client | None = None) -> tuple[list[Document], str]:
    own = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "georag"})
    try:
        try:
            docs, source = from_planetary_computer(client), "planetary-computer"
        except httpx.HTTPError:
            docs, source = from_aws_registry(client), "aws-open-data-registry"
        return docs + extra_datasets(), source
    finally:
        if own:
            client.close()
