import os
import shutil
import subprocess
import logging
from pathlib import Path
import docker
from docker.errors import DockerException

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebsiteHandler:
    def __init__(self, docker_client=None):
        self.docker_client = docker_client or docker.from_env()
        self.website_dir = Path("website")
        self.build_dir = self.website_dir / "build"
        self.test_dir = self.website_dir / "test"

    def build_website(self):
        """Build the website using Docker."""
        try:
            # Create build directory if it doesn't exist
            self.build_dir.mkdir(parents=True, exist_ok=True)

            # Create Dockerfile for building
            dockerfile_content = """
FROM node:16-alpine as builder
WORKDIR /app
COPY website/package*.json ./
RUN npm install
COPY website/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""
            with open(self.website_dir / "Dockerfile", "w") as f:
                f.write(dockerfile_content)

            # Build Docker image
            if self.docker_client:
                image, logs = self.docker_client.images.build(
                    path=str(self.website_dir),
                    tag="chatops-website:latest",
                    rm=True
                )
                return True, "Website built successfully!"
            else:
                return False, "Docker client not initialized"

        except Exception as e:
            logger.error(f"Error building website: {str(e)}")
            return False, f"Error building website: {str(e)}"

    def test_website(self):
        """Run tests on the website."""
        try:
            # Create test directory if it doesn't exist
            self.test_dir.mkdir(parents=True, exist_ok=True)

            # Create a simple test script
            test_script = """
const { test, expect } = require('@playwright/test');

test('Website loads successfully', async ({ page }) => {
    await page.goto('http://localhost:80');
    const title = await page.title();
    expect(title).toBeTruthy();
});

test('All links are working', async ({ page }) => {
    await page.goto('http://localhost:80');
    const links = await page.$$('a');
    for (const link of links) {
        const href = await link.getAttribute('href');
        if (href && !href.startsWith('#')) {
            const response = await page.goto(href);
            expect(response.status()).toBe(200);
        }
    }
});
"""
            with open(self.test_dir / "website.spec.js", "w") as f:
                f.write(test_script)

            # Run tests using Docker
            if self.docker_client:
                container = self.docker_client.containers.run(
                    "chatops-website:latest",
                    detach=True,
                    ports={'80/tcp': 80}
                )
                
                # Run Playwright tests
                test_result = subprocess.run(
                    ["npx", "playwright", "test"],
                    cwd=str(self.test_dir),
                    capture_output=True,
                    text=True
                )
                
                # Stop and remove the test container
                container.stop()
                container.remove()
                
                if test_result.returncode == 0:
                    return True, "All tests passed successfully!"
                else:
                    return False, f"Tests failed: {test_result.stderr}"
            else:
                return False, "Docker client not initialized"

        except Exception as e:
            logger.error(f"Error testing website: {str(e)}")
            return False, f"Error testing website: {str(e)}"

    def deploy_website(self, website_name="my-website"):
        """Deploy the website using Docker."""
        try:
            # Stop and remove existing container if it exists
            try:
                container = self.docker_client.containers.get(f"{website_name}-container")
                container.stop()
                container.remove()
                logger.info(f"Stopped and removed existing container: {website_name}-container")
            except docker.errors.NotFound:
                logger.info(f"No existing container found: {website_name}-container")

            # Ensure website directory exists
            if not self.website_dir.exists():
                return False, f"❌ Website directory not found at: {self.website_dir}"

            # Build Docker image
            logger.info(f"Building image {website_name}-image from {self.website_dir}")
            image, logs = self.docker_client.images.build(
                path=str(self.website_dir),
                tag=f"{website_name}-image",
                rm=True,
                dockerfile="Dockerfile"
            )

            # Run the container
            logger.info(f"Starting container {website_name}-container")
            container = self.docker_client.containers.run(
                f"{website_name}-image",
                detach=True,
                ports={'80/tcp': 8089},
                name=f"{website_name}-container",
                restart_policy={"Name": "always"}
            )

            # Verify container is running
            container.reload()
            if container.status != "running":
                return False, f"❌ Container failed to start. Status: {container.status}"

            return True, f"""✅ Successfully deployed website!
• Container: {website_name}-container
• Image: {website_name}-image
• Port: 8089
• Access at: http://localhost:8089"""

        except Exception as e:
            logger.error(f"Error deploying website: {str(e)}")
            return False, f"❌ Failed to deploy website: {str(e)}"

    def cleanup(self):
        """Clean up build artifacts."""
        try:
            if self.build_dir.exists():
                shutil.rmtree(self.build_dir)
            if self.test_dir.exists():
                shutil.rmtree(self.test_dir)
            return True, "Cleanup completed successfully"
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            return False, f"Error during cleanup: {str(e)}" 