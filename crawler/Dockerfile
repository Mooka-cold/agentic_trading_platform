FROM python:3.10-slim

WORKDIR /app

COPY crawler/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY crawler/ /app/
COPY shared/ /app/shared/

ENV PYTHONPATH=/app:/app/shared

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
