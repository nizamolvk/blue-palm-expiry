FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY task2_api ./task2_api
COPY clean_items.csv ./clean_items.csv

EXPOSE 8000

CMD ["sh", "-c", "python -m task2_api.load_data && uvicorn task2_api.main:app --host 0.0.0.0 --port 8000"]
