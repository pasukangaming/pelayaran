FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Hugging Face Spaces Docker containers run on port 7860
EXPOSE 7860

# Run Flask app with gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]
