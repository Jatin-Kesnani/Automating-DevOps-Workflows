#!/bin/bash

# Stop and remove existing container if it exists
docker stop website-users-container 2>/dev/null
docker rm website-users-container 2>/dev/null

# Build the Docker image
docker build -t website-users-image .

# Run the container
docker run -d -p 8082:80 --name website-users-container website-users-image

# Check if container is running
docker ps | grep website-users-container

echo "Website should be accessible at http://localhost:8082" 