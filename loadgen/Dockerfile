FROM python:3.12-slim
WORKDIR /srv
RUN pip install --no-cache-dir httpx==0.28.1 prometheus-client==0.21.1
COPY loadgen.py .
CMD ["python", "-u", "loadgen.py"]
