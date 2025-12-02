FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy German model
RUN python -m spacy download de_core_news_lg

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

CMD ["python", "app.py"]
