# One container: builds the React app, then Node serves API + web. Not built in my sandbox: test with `docker build .`
FROM node:22-slim AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM node:22-slim
WORKDIR /app
COPY api/package*.json api/
RUN cd api && npm ci --omit=dev
COPY api/ api/
COPY sql/ sql/
COPY --from=web /web/dist web/dist
ENV NODE_ENV=production PORT=3000 DATABASE_PATH=/data/plain.db SEED_ON_EMPTY=false
VOLUME /data
EXPOSE 3000
CMD ["node", "--disable-warning=ExperimentalWarning", "api/src/server.js"]
