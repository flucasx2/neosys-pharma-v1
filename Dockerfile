FROM python:3.14-slim-bookworm@sha256:a66d3a463d0be3cc537c269b0d3418746dda512417a975559a0eaa8a6406baaf AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /opt/neosys
RUN groupadd --gid 10001 neosys && useradd --uid 10001 --gid neosys --create-home neosys
COPY docker/entrypoint.py /opt/neosys/docker/entrypoint.py

FROM base AS app
# Hash-locked wheels for Linux CPython 3.14 / amd64.
COPY requirements/runtime.lock /opt/neosys/requirements/runtime.lock
RUN python -m pip install --only-binary=:all: --require-hashes -r requirements/runtime.lock
COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-deps --no-build-isolation .
COPY alembic.ini ./
COPY migrations ./migrations
USER neosys
ENTRYPOINT ["python", "/opt/neosys/docker/entrypoint.py"]
CMD ["python", "-m", "uvicorn", "neosys_pharma.presentation.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/opt/neosys/src"]

FROM base AS tests
COPY requirements/tests.lock /opt/neosys/requirements/tests.lock
RUN python -m pip install --only-binary=:all: --require-hashes -r requirements/tests.lock
COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-deps --no-build-isolation .
COPY alembic.ini ./
COPY migrations ./migrations
COPY tests ./tests
USER neosys
ENTRYPOINT ["python", "/opt/neosys/docker/entrypoint.py"]
# PostgreSQL-native suites remain gated until their disposable DB orchestration exists.
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
