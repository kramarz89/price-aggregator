# Playwright's official image matches playwright==1.60.0 from requirements.txt and
# ships Chromium plus all system libraries, so we skip apt installs and browser downloads.
FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

WORKDIR /app

# Install Python deps in their own layer so it stays cached across code-only changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code. .dockerignore keeps out .env, tokens, tests, the venv and demo assets.
COPY . .

# config.load_dotenv() is a no-op without a .env file, so config reads the real
# environment variables that TrueNAS injects into the container.
EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
