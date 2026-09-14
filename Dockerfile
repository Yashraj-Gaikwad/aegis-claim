FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TWIN_MODE=true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY aegis/ aegis/
COPY policies/ policies/
COPY tests/ tests/
COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "aegis.server:app", "--host", "0.0.0.0", "--port", "8000"]
