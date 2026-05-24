FROM python:3.12-slim

WORKDIR /workspace

# Ensure Python can always find the worker package regardless of how the
# container is invoked (docker compose run, k8s job, etc.).
ENV PYTHONPATH=/workspace

COPY requirements.txt ./
RUN if [ -s requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Copy the worker package so it can be imported as worker.app.*
# The __init__.py at the worker root is required for the package to resolve.
COPY __init__.py ./worker/__init__.py
COPY app ./worker/app

# Remove any stale compiled bytecache that may have been copied from the
# host workspace. This ensures Python always uses the source files above.
RUN find /workspace -name '*.pyc' -delete \
    && find /workspace -name '__pycache__' -type d -exec rm -rf {} + \
    ; true

CMD ["python", "-m", "worker.app.cli", "noop"]
