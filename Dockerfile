FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file 
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Set environment variable for port
ENV PORT=8002

# Expose the port
EXPOSE 8002

# Run the flask application
CMD ["python", "app.py"]