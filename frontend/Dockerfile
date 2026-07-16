# Frontend image: Next.js 15 production server.
# Build context is ./frontend. Kept single-stage for simplicity (not size-optimized).
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3000

# The /api/* rewrite target (next.config.mjs) is read at server start from BACKEND_URL.
# In compose this is set to the backend service DNS name.
ENV BACKEND_URL=http://backend:8000

CMD ["npm", "run", "start"]
