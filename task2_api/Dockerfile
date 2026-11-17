FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY task2_api ./task2_api
COPY task4_agent ./task4_agent
COPY clean_items.csv ./clean_items.csv
COPY task2_api/docker-start.sh /docker-start.sh

EXPOSE 8000

CMD ["sh", "/docker-start.sh"]
