# Use a minimal web server image
FROM nginx:alpine

# Remove default nginx HTML files
RUN rm -rf /usr/share/nginx/html/*

# Copy your HTML/CSS into nginx public folder
COPY . /usr/share/nginx/html

# Expose port
EXPOSE 8089