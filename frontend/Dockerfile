# Multistage Dockerfile for beacon-library frontend (Vite/React/TS)

# -- Dev stage (with Node for hot-reload)
FROM node:20-slim as dev
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host"]

# -- Build stage
FROM node:20-slim as build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend .
RUN npm run build

# -- Production stage (Nginx for serving static files)
FROM nginx:alpine as prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
