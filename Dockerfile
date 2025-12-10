# Use Python 3.12
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt python-dotenv

# Copy the full application code
COPY . .

# Set environment variables
ENV PORT=8080
ENV ENV_FILE=/secrets/.env

# Run uvicorn, load .env from ENV_FILE
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
