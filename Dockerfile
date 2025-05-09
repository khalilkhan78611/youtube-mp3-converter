# Use a slim Python base image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements file to install dependencies
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port your app runs on
EXPOSE 8000

# Set environment variables (optional, adjust as needed)
ENV PYTHONUNBUFFERED=1

# Command to run the application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
