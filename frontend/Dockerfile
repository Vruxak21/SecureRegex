FROM node:20-slim

WORKDIR /app

# Install deps (cached layer)
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps

# Copy source
COPY . .

EXPOSE 5173

# Start Vite dev server bound to all interfaces so Docker can forward the port
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
