# Use the smallest official Python runtime
FROM python:3.11.11-alpine

# Set environment variables for Python to optimize runtime and set timezone
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata

# Install tzdata to configure timezone and any build dependencies
RUN apk add --no-cache tzdata

# Set working directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application code into the container
COPY . .

# Expose port 5000 for the Flask application
EXPOSE 5000

# Run the Flask application with Gunicorn
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "app:app"]
