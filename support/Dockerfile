# Support desk — one FastAPI process over SQLite, uploads on a volume.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 SUPPORT_DATA=/data
COPY support/requirements.txt /app/support/requirements.txt
RUN pip install --no-cache-dir -r /app/support/requirements.txt
COPY support /app/support
VOLUME ["/data"]
EXPOSE 3003
CMD ["uvicorn", "support.app:app", "--host", "0.0.0.0", "--port", "3003", "--proxy-headers"]
