# Build from the repository root:  docker build -f eternalai/Dockerfile .
FROM python:3.12-slim
WORKDIR /srv
COPY eternalai/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY eternalai ./eternalai
# Frozen model artifacts and their metadata. If none are present the backend reports rule fallbacks in /status.
COPY models/artifacts ./models/artifacts
# Optional reviewed/unreviewed runbook text for retrieval (derived from the training workbook; not committed).
COPY data/processed/knowledge_base.cs[v] ./data/processed/
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "eternalai.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
