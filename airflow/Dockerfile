# Airflow 3.4 on Python 3.13, with the corrector in an environment of its own.
# Built by docker-compose.yaml, with the repository root as the build context.
FROM apache/airflow:3.4.0-python3.13

# uv, the version CI uses, installs the corrector exactly as uv.lock says.
# The base image has a uv of its own earlier on PATH, so this one is called
# by its full path below.
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv

USER root
RUN install -d -o airflow -g root /opt/corrector
USER airflow
WORKDIR /opt/corrector

COPY --chown=airflow:root pyproject.toml uv.lock .python-version README.md LICENSE lexicon_filter.py ./
COPY --chown=airflow:root scripts ./scripts

# Its own environment, so Airflow never imports spaCy and the two sets of
# dependencies can't clash. Without the stanza extra, PyTorch stays out.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
RUN --mount=type=cache,target=/home/airflow/.cache/uv,uid=50000,gid=0 \
    /usr/local/bin/uv sync --locked --no-dev --no-editable \
 && rm -rf build ./*.egg-info \
 && .venv/bin/greek-correct --help > /dev/null

WORKDIR /opt/airflow
