# Build from the repository root:  docker build -f eternalai/Dockerfile .
FROM python:3.12-slim
WORKDIR /srv
COPY eternalai/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY eternalai ./eternalai
# Frozen model artifacts and their metadata. If none are present the backend reports rule fallbacks in /status.
COPY models/artifacts ./models/artifacts
# Runbook text for retrieval is derived from the training workbook and is not committed, so the image does not contain it.
# Provide it at run time with a bind mount and EAI_KNOWLEDGE_CSV (see docs/DEMO.md); without it retrieval says so.
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "eternalai.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
