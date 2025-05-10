# Stop and remove existing container if it exists
docker stop website-users-container 2>$null
docker rm website-users-container 2>$null

# Build the Docker image
docker build -t website-users-image .

# Run the container
docker run -d -p 8089:80 --name website-users-container website-users-image

# Check if container is running
docker ps | Select-String website-users-container

Write-Host "Website should be accessible at http://localhost:8089" 