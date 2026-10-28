# Design notes

Short records of the choices that shaped GeoRAG Copilot, with the alternatives considered.

## Corpus: arXiv metadata snapshot as the default source

The build machine had no route to OpenAlex, publisher sites or arXiv's own servers, but it could
reach the Hugging Face Hub. arXiv publishes its metadata — titles, authors and abstracts — under
CC0, and `librarian-bots/arxiv-metadata-snapshot` mirrors it weekly as Parquet. That makes a
corpus that is legally clean, reproducible from public files and small enough to commit only as
a manifest. The trade-off is depth: abstracts carry the claims of a paper but not its method
details, tables or figures. The OpenAlex path (CC BY / CC0 full text, PDF parsing with
`pymupdf4llm`) is implemented behind `georag corpus --source openalex` for machines that can
reach it.

Papers are selected per domain with regular-expression rules (`configs/domains.yaml`): a paper
must match a domain's required terms and is ranked by how many related terms it mentions, with
title matches counting most. Domains are filled round-robin so a paper that fits two domains
does not crowd out a third.

## Vector store: an exact float16 matrix

With roughly ten thousand chunks an exact inner-product search takes about a millisecond and
needs no server, while filtering by domain is a boolean mask. Qdrant or LanceDB become worth
their operational cost around a few hundred thousand chunks; `DenseIndex.search` is the only
function that would change.

## Fusion: reciprocal rank fusion

BM25 scores are unbounded, cosine similarities are not, and graph scores are walk weights.
RRF (k = 60) needs no calibration between them. The graph list gets weight 0.6 because it is a
recall booster: it surfaces passages about neighbouring concepts, which helps cross-domain
questions but adds noise to narrow factual ones. The reranker then decides.

## Knowledge graph: glossary-anchored co-mentions

Small local models extract entities and relations unreliably; LightRAG's authors recommend
32B-class models for graph extraction. GeoRAG anchors the graph on a curated glossary of 181
terms with aliases (case-sensitive for acronyms such as SAR or DSM), links entities that are
mentioned in the same chunk, and weights edges by normalised PMI so that pairs of ubiquitous
terms do not dominate. Every edge keeps its supporting chunks, which is what makes an Explore
answer checkable. Schema-constrained LLM extraction can extend the node set on a larger GPU.

## Grounding: the reranker as a judge

The Qwen3 reranker is already loaded for retrieval, so the support check costs one extra batch
of cross-encoder calls per answer: each sentence is scored against the passages it cites, and
sentences below P(yes) = 0.25 are flagged. The same score on the best retrieved passage decides
refusal (below 0.15 the agent declines without calling the generator). Thresholds were set on
the fixture corpus and a handful of manual queries, not tuned on the benchmark.

## Analyze: plans, not programs

The model fills a typed `AnalysisPlan` (task, place, months, index, threshold, cloud limit).
Geography and dates are never taken from the model: the bounding box comes from the gazetteer
or the user, and months parsed from the request override the model's. Jinja templates turn the
plan into a short script that calls `georag.geo.eo`. Repairs change the plan, not the code —
wider cloud limits, a neighbouring month, fewer scenes — so every attempt runs through the same
audited path.

Scenes come from the Planetary Computer STAC API when it is reachable and otherwise from the
public `sentinel-cogs` bucket, whose STAC items sit beside the COGs; the bucket listing is the
catalogue. Clouds and shadows are removed with the scene classification layer, and monthly
composites are pixel-wise medians of the clearest scenes. Reflectance scale and offset are read
from each item (`raster:bands`), which handles the +1000 offset introduced with processing
baseline 04.00 in January 2022.

## Sandbox: layered, because no single layer is enough

A static AST check (import allow-list, no `exec`/`eval`/dunder access, relative paths only),
a separate `python -I` process with CPU, memory and file-size limits and a clean environment,
PEP 578 audit hooks against process creation, writes outside the run folder and lookups of
non-allow-listed hosts, and a URL check inside the EO helpers. GDAL's own HTTP client sits below
the audit hooks, which is why the URL check exists; the Docker recipe in `docker/` removes that
gap entirely.

## Evaluation

Synthetic questions are cheap and cover the corpus evenly, but they share the generator's style
and the gold passage's wording. GeoRAG-Bench therefore also has cross-domain questions (two
passages, two fields), hand-written unanswerable questions, and Analyze tasks scored against an
independent reference (JRC Global Surface Water) rather than against the model's own output.
