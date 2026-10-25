# Build from the repository root:  docker build -f engine/Dockerfile .
FROM python:3.12-slim
WORKDIR /srv
COPY engine/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY engine ./engine
# Frozen model artifacts and their metadata. If none are present the backend reports rule fallbacks in /status.
COPY ml/models/artifacts ./ml/models/artifacts
# Knowledge base and measured fix outcomes (Package C; built by tools/build_kb.py from the owner's workbook, which is not in the image).
COPY ml/data/kb ./ml/data/kb
# Retrieval of knowledge-base text uses ml/data/kb/knowledge_base.csv (rows flagged unreviewed); EAI_KNOWLEDGE_CSV overrides it.
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "engine.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
