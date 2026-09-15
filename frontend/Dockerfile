# Frontend Dockerfile — Multi-stage React + Vite + CesiumJS
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency specifications
COPY package.json package-lock.json* ./

# Install project dependencies
RUN npm ci

# Copy application source code
COPY . .

# Build production bundle
RUN npm run build

# Stage 2 — NGINX web server to serve static production bundle
FROM nginx:alpine

# Copy NGINX configuration for Single Page Application routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
