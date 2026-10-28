"""Open technical documentation: specifications and library manuals.

Each source is fetched from the project's own repository and keeps its licence, recorded per
file in the manifest. Markdown, reStructuredText and AsciiDoc are split on headings so a chunk
never straddles two sections.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import httpx

from georag.schemas import Document

RAW = "https://raw.githubusercontent.com"


@dataclass(frozen=True)
class DocSource:
    project: str
    licence: str
    repo: str
    paths: tuple[str, ...]
    web: str  # human-facing documentation URL


DOC_SOURCES: tuple[DocSource, ...] = (
    DocSource(
        "STAC specification",
        "Apache-2.0",
        "radiantearth/stac-spec/master",
        (
            "overview.md",
            "item-spec/item-spec.md",
            "collection-spec/collection-spec.md",
            "catalog-spec/catalog-spec.md",
            "best-practices.md",
            "commons/assets.md",
        ),
        "https://github.com/radiantearth/stac-spec",
    ),
    DocSource(
        "STAC API",
        "Apache-2.0",
        "radiantearth/stac-api-spec/main",
        ("item-search/README.md",),
        "https://github.com/radiantearth/stac-api-spec",
    ),
    DocSource(
        "PDAL",
        "BSD-3-Clause",
        "PDAL/PDAL/master",
        (
            "doc/about.md",
            "doc/pipeline.md",
            "doc/stages/readers.las.md",
            "doc/stages/filters.smrf.md",
            "doc/stages/filters.csf.md",
            "doc/stages/filters.outlier.md",
            "doc/stages/filters.hag_nn.md",
            "doc/stages/writers.gdal.md",
        ),
        "https://pdal.io",
    ),
    DocSource(
        "GDAL",
        "MIT",
        "OSGeo/gdal/master",
        (
            "doc/source/user/raster_data_model.rst",
            "doc/source/user/virtual_file_systems.rst",
            "doc/source/drivers/raster/cog.rst",
            "doc/source/programs/gdalwarp.rst",
            "doc/source/programs/gdal_translate.rst",
            "doc/source/programs/gdalbuildvrt.rst",
        ),
        "https://gdal.org",
    ),
    DocSource(
        "rasterio",
        "BSD-3-Clause",
        "rasterio/rasterio/main",
        (
            "docs/quickstart.rst",
            "docs/topics/windowed-rw.rst",
            "docs/topics/reproject.rst",
            "docs/topics/virtual-warping.rst",
            "docs/topics/masks.rst",
            "docs/topics/vsi.rst",
        ),
        "https://rasterio.readthedocs.io",
    ),
    DocSource(
        "pystac-client",
        "Apache-2.0",
        "stac-utils/pystac-client/main",
        ("docs/usage.rst",),
        "https://pystac-client.readthedocs.io",
    ),
    DocSource(
        "odc-stac",
        "Apache-2.0",
        "opendatacube/odc-stac/develop",
        ("README.rst",),
        "https://odc-stac.readthedocs.io",
    ),
    DocSource(
        "CityJSON",
        "CC-BY-4.0",
        "cityjson/specs/main",
        ("README.md",),
        "https://www.cityjson.org",
    ),
    DocSource(
        "OGC 3D Tiles",
        "CC-BY-4.0",
        "CesiumGS/3d-tiles/main",
        ("specification/README.adoc", "specification/TileFormats/README.adoc", "README.md"),
        "https://github.com/CesiumGS/3d-tiles",
    ),
    DocSource(
        "TerraTorch",
        "Apache-2.0",
        "IBM/terratorch/main",
        ("README.md", "docs/index.md", "docs/guide/quick_start.md"),
        "https://ibm.github.io/terratorch",
    ),
    DocSource(
        "Planetary Computer",
        "MIT",
        "microsoft/PlanetaryComputer/main",
        ("README.md",),
        "https://planetarycomputer.microsoft.com",
    ),
)

_HEADING_PATTERNS = (
    re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$"),  # markdown
    re.compile(r"^(={1,4})\s+(.+?)\s*$"),  # asciidoc
)
_RST_UNDERLINE = re.compile(r"^([=\-~^\"'`#*+])\1{2,}\s*$")


def _strip_markup(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)  # images
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # md links
    text = re.sub(r"`([^`<]+?)\s*<[^>]+>`_+", r"\1", text)  # rst links
    text = re.sub(r":(?:ref|doc|class|func|meth|py:\w+):`([^`]+)`", r"\1", text)
    text = re.sub(r"^\.\. [\w:-]+::.*$", " ", text, flags=re.M)  # rst directives
    text = re.sub(r"^\s*:\w[\w-]*:.*$", " ", text, flags=re.M)  # rst options
    text = re.sub(r"\[\[[^\]]*\]\]|<<[^>]*>>", " ", text)  # asciidoc anchors and xrefs
    text = re.sub(r"\{[a-z-]+\}", " ", text)  # asciidoc attributes
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sections(raw: str, default_title: str) -> list[tuple[str, str]]:
    """Split markdown/rst/asciidoc text into (heading, body) pairs."""
    lines = raw.splitlines()
    sections: list[tuple[str, list[str]]] = [(default_title, [])]
    in_code = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith(("```", "----", "....")):
            in_code = not in_code
        heading = None
        if not in_code:
            for pat in _HEADING_PATTERNS:
                m = pat.match(line)
                if m:
                    heading = m.group(2)
                    break
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if (
                heading is None
                and line.strip()
                and _RST_UNDERLINE.match(nxt)
                and len(nxt.strip()) >= len(line.strip()) - 2
            ):
                heading = line.strip()
                i += 1
            elif (
                heading is None
                and _RST_UNDERLINE.match(line)
                and i + 2 < len(lines)
                and _RST_UNDERLINE.match(lines[i + 2])
            ):
                heading = lines[i + 1].strip()  # overlined rst title
                i += 2
        if heading:
            sections.append((_strip_markup(heading), []))
        else:
            sections[-1][1].append(line)
        i += 1
    out = []
    for head, body in sections:
        text = _strip_markup("\n".join(body))
        if len(text) >= 120:
            out.append((head, text))
    return out


def fetch_docs(client: httpx.Client | None = None) -> list[Document]:
    own = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "georag"})
    docs: list[Document] = []
    try:
        for src in DOC_SOURCES:
            for path in src.paths:
                url = f"{RAW}/{src.repo}/{path}"
                resp = client.get(url)
                if resp.status_code != 200:
                    continue
                raw = resp.text
                stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                fallback = f"{src.project}: {stem.replace('-', ' ').replace('_', ' ')}"
                sections = split_sections(raw, fallback)
                if not sections:
                    continue
                first = next((h for h, _ in sections if h != fallback), None)
                title = (
                    f"{src.project}: {first}"
                    if first and not first.startswith(src.project)
                    else (first or fallback)
                )
                doc_hash = hashlib.sha1(url.encode()).hexdigest()[:10]
                docs.append(
                    Document(
                        doc_id=f"docs:{src.project.lower().replace(' ', '-')}:{doc_hash}",
                        source="docs",
                        title=title,
                        text="\n\n".join(body for _, body in sections),
                        domain="docs",
                        url=f"https://github.com/{src.repo.split('/')[0]}/{src.repo.split('/')[1]}/blob/{src.repo.split('/')[2]}/{path}",
                        licence=src.licence,
                        authors=[src.project],
                        sections=sections,
                    )
                )
    finally:
        if own:
            client.close()
    return docs
