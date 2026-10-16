FROM python:3.12-slim
ARG SERVICE
ARG RELEASE=good
ARG VERSION=v1
ARG RELEASE_SEQ=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common ./common
COPY ${SERVICE} ./service
ENV SERVICE=${SERVICE} RELEASE_FLAVOR=${RELEASE} APP_VERSION=${VERSION} RELEASE_SEQ=${RELEASE_SEQ}
LABEL eai.service=${SERVICE} eai.version=${VERSION} eai.release_seq=${RELEASE_SEQ}
EXPOSE 8000
CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
