FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN if [ -s requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

COPY app ./app

CMD ["python", "-m", "app.cli", "noop"]
