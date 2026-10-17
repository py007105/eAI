# Build from the repository root:  docker build -f dashboard/Dockerfile .
FROM python:3.12-slim
WORKDIR /srv
COPY dashboard/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY dashboard ./dashboard
ENV PYTHONUNBUFFERED=1 PORT=8050
EXPOSE 8050
CMD ["python", "dashboard/app.py"]
