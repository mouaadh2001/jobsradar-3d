FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000

CMD ["sh", "-c", "gunicorn -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} main:app"]
