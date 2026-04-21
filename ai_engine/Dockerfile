FROM python:3.10-slim

WORKDIR /app

COPY ai_engine/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

COPY ai_engine/ /app/
COPY shared/ /app/shared/

ENV PYTHONPATH=/app:/app/shared

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
