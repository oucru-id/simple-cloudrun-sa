# Use the official Python image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Set environment variables
ENV PORT=8080

# Expose the port
EXPOSE 8080

# Use gunicorn as the production server
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app