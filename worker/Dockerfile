FROM python:3.12-slim

WORKDIR /workspace

COPY requirements.txt ./
RUN if [ -s requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Copy the worker package so it can be imported as worker.app.*
# The __init__.py at the worker root is required for the package to resolve.
COPY __init__.py ./worker/__init__.py
COPY app ./worker/app

CMD ["python", "-m", "worker.app.cli", "noop"]
