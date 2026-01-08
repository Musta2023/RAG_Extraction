# Use an official Python runtime as a parent image
FROM python:3.11-slim-bookworm

# Set the working directory in the containerr

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update \
    && apt-get -y install netcat-openbsd \
    && apt-get clean

# Install Python dependencies
COPY ./requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY ./app /app/app
COPY ./tests /app/tests
COPY ./evaluation /app/evaluation
COPY ./evaluation /app/evaluation

# Copy the .env file
COPY ./.env.example ./.env

# Expose the port the app runs on
EXPOSE 8000

# Add a script to wait for Redis
COPY ./scripts/wait-for-redis.sh /wait-for-redis.sh
RUN chmod +x /wait-for-redis.sh

# Define the command to run the application
# Use a production-ready server like uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
