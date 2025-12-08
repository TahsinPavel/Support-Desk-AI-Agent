FROM python:3.11-slim

WORKDIR /app

# Install dependencies first
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy your full backend code
COPY . .

# Cloud Run expects the app to listen on PORT=8080
ENV PORT=8080

# Start FastAPI with correct module path
CMD ["uvicorn", "ai_support_desk.main:app", "--host", "0.0.0.0", "--port", "8080"]
