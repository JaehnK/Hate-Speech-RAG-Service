import { defineRailway, github, postgres, preserve, project, service, volume } from "railway/iac";

export default defineRailway(() => {
  const HateSpeechRAGService = github("JaehnK/Hate-Speech-RAG-Service", { checkSuites: false });

  const Postgres = postgres("Postgres", { region: "asia-southeast1-eqsg3a" });
  const backendVolume = volume("backend-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "asia-southeast1-eqsg3a", sizeMB: 500 });
  const workerVolumeA1vw = volume("worker-volume-A1vw", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "asia-southeast1-eqsg3a", sizeMB: 8192 });
  const postgresVolume = volume("postgres-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "asia-southeast1-eqsg3a", sizeMB: 500 });
  const backend = service("backend", {
    source: github("JaehnK/Hate-Speech-RAG-Service", { checkSuites: true }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/Dockerfile.backend" },
    preDeployCommand: "alembic upgrade head",
    replicas: { "asia-southeast1-eqsg3a": 1 },
    volumeMounts: {
      "/data": backendVolume,
    },
    env: {
      ADMIN_TOKEN: preserve(),
      API_DOCS_ENABLED: preserve(),
      API_KEY_ENCRYPTION_KEY: preserve(),
      APP_ENV: preserve(),
      DATABASE_URL: preserve(),
      EMBEDDING_MODEL: preserve(),
      EMBEDDING_PROVIDER: preserve(),
      FRONTEND_ORIGIN: preserve(),
      GOOGLE_CLIENT_ID: preserve(),
      GOOGLE_CLIENT_SECRET: preserve(),
      GOOGLE_OAUTH_REDIRECT_URI: preserve(),
      LLM_MODEL: preserve(),
      LLM_PROVIDER: preserve(),
      PIPELINE_MODE: preserve(),
      PORT: preserve(),
      RAG_EMBEDDING_CONCURRENCY: preserve(),
      RAG_EXECUTION_MODE: preserve(),
      RAG_ITEM_CONCURRENCY: preserve(),
      RAG_LLM_CONCURRENCY: preserve(),
      REPORT_STORAGE_DIR: preserve(),
      SESSION_COOKIE_SECURE: preserve(),
      UPSTAGE_API_KEY: preserve(),
      YOUTUBE_API_KEY: preserve(),
    },
  });
  const front = service("front", {
    source: HateSpeechRAGService,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/Dockerfile.frontend" },
    replicas: { "asia-southeast1-eqsg3a": 1 },
    env: {
      API_UPSTREAM: preserve(),
      FRONTEND_ORIGIN: preserve(),
      GOOGLE_OAUTH_REDIRECT_URI: preserve(),
      PORT: preserve(),
      SESSION_COOKIE_SECURE: preserve(),
    },
  });
  const worker = service("worker", {
    source: HateSpeechRAGService,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/Dockerfile.backend" },
    start: "python -m app.worker_main",
    replicas: { "asia-southeast1-eqsg3a": 1 },
    volumeMounts: {
      "/data": workerVolumeA1vw,
    },
    env: {
      ADMIN_TOKEN: preserve(),
      API_KEY_ENCRYPTION_KEY: preserve(),
      APP_ENV: preserve(),
      CHROMA_PERSIST_DIRECTORY: preserve(),
      DATABASE_URL: preserve(),
      EMBEDDING_MODEL: preserve(),
      EMBEDDING_PROVIDER: preserve(),
      FRONTEND_ORIGIN: preserve(),
      GOOGLE_CLIENT_ID: preserve(),
      GOOGLE_CLIENT_SECRET: preserve(),
      GOOGLE_OAUTH_REDIRECT_URI: preserve(),
      LLM_MODEL: preserve(),
      LLM_PROVIDER: preserve(),
      PIPELINE_MODE: preserve(),
      PORT: preserve(),
      RAG_EMBEDDING_CONCURRENCY: preserve(),
      RAG_EXECUTION_MODE: preserve(),
      RAG_ITEM_CONCURRENCY: preserve(),
      RAG_LLM_CONCURRENCY: preserve(),
      SESSION_COOKIE_SECURE: preserve(),
      UPSTAGE_API_KEY: preserve(),
      YOUTUBE_API_KEY: preserve(),
    },
  });

  return project("hatescope", {
    resources: [Postgres, backend, front, worker, backendVolume, workerVolumeA1vw, postgresVolume],
  });
});
