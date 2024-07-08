# Use an official Python runtime as a parent image
FROM --platform=linux/arm64 python:3.11.9-alpine3.20

# Set the working directory in the container
WORKDIR /app

# Copy all files from the current directory to the container's working directory
COPY . .

# Install necessary system packages
RUN apk update && apk add --no-cache \
    build-base \
    && rm -rf /var/cache/apk/*
    
# Install any Python dependencies needed for your D-Bus application
# For example:
RUN pip install -r requirements.txt

# Specify the command to run your application
# For example:
CMD ["python", "app.py"]
