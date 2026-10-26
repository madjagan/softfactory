# Ideas portal — one FastAPI process over SQLite, uploads on a volume.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 IDEAS_DATA=/data
COPY ideas/requirements.txt /app/ideas/requirements.txt
RUN pip install --no-cache-dir -r /app/ideas/requirements.txt
COPY ideas /app/ideas
VOLUME ["/data"]
EXPOSE 3004
CMD ["uvicorn", "ideas.app:app", "--host", "0.0.0.0", "--port", "3004", "--proxy-headers"]
