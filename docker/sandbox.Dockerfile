# Stronger isolation for Analyze mode: run generated scripts in a throwaway container.
#   docker build -f docker/sandbox.Dockerfile -t georag-sandbox .
#   docker run --rm --memory=4g --cpus=2 --pids-limit=128 --read-only \
#     --tmpfs /tmp -v "$RUN_DIR":/run -w /run \
#     --network=georag-egress georag-sandbox python -I analysis.py
# where `georag-egress` is a Docker network whose egress proxy only allows the STAC and
# asset hosts listed in configs/default.yaml (sandbox.allowed_hosts).
FROM python:3.12-slim
RUN pip install --no-cache-dir numpy rasterio pyproj shapely matplotlib httpx
COPY src/georag /opt/georag/georag
ENV PYTHONPATH=/opt/georag MPLBACKEND=Agg
RUN useradd --create-home runner
USER runner
