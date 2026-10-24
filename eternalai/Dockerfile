# Build from the repository root:  docker build -f eternalai/Dockerfile .
FROM python:3.12-slim
WORKDIR /srv
COPY eternalai/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY eternalai ./eternalai
# Frozen model artifacts and their metadata. If none are present the backend reports rule fallbacks in /status.
COPY models/artifacts ./models/artifacts
# Knowledge base and measured fix outcomes (Package C; built by scripts/build_kb.py from the owner's workbook, which is not in the image).
COPY data/kb ./data/kb
# Retrieval of knowledge-base text uses data/kb/knowledge_base.csv (rows flagged unreviewed); EAI_KNOWLEDGE_CSV overrides it.
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "eternalai.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
