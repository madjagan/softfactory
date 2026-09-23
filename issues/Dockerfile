# Issue tracker — one FastAPI process over SQLite, uploads on a volume.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ISSUES_DATA=/data
COPY issues/requirements.txt /app/issues/requirements.txt
RUN pip install --no-cache-dir -r /app/issues/requirements.txt
COPY issues /app/issues
COPY tools/factory.py /app/tools/factory.py
# The optional seeder reads these; a customer board never runs it.
COPY factory.yaml /app/factory.yaml
COPY docs/issues_log.md /app/docs/issues_log.md
COPY docs/issues_classified.json /app/docs/issues_classified.json
VOLUME ["/data"]
EXPOSE 3002
CMD ["uvicorn", "issues.app:app", "--host", "0.0.0.0", "--port", "3002", "--proxy-headers"]
