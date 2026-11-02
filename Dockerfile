FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements-desk.lock ./
RUN pip install --disable-pip-version-check -r requirements-desk.lock
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-deps .
COPY data ./data
COPY ontology ./ontology
COPY exports/atlas ./exports/atlas
RUN groupadd --gid 10001 analyst && useradd --uid 10001 --gid analyst --no-create-home analyst && mkdir /data && chown analyst:analyst /data
USER 10001:10001
ENV SYRIA_DESK_DATABASE=/data/desk.sqlite3 SYRIA_DESK_ALLOWED_HOSTS=localhost,127.0.0.1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3)" || exit 1
CMD ["uvicorn","syria_analysis.desk.app:create_app","--factory","--host","0.0.0.0","--port","8000","--workers","1","--no-access-log"]
