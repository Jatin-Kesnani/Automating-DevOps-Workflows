# Use Nginx as the base image
FROM nginx:alpine

# Copy the website files to Nginx's default serving directory
COPY website/ /usr/share/nginx/html/

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"] 