FROM python:3.11-slim
WORKDIR /app
COPY scheduler/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY scheduler/ /app/
COPY shared/ /app/shared/
ENV PYTHONPATH=/app:/app/shared
CMD ["python", "main.py"]
