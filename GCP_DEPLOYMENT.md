# GCP Deployment Setup for PatentIQ

This project is configured to deploy both services to Google Cloud Run with a Cloud SQL PostgreSQL backend.

## Files added

- `apps/api/Dockerfile` — builds the FastAPI backend
- `apps/web/Dockerfile` — builds the Next.js frontend
- `cloudbuild.yaml` — builds both Docker images using Cloud Build
- `.dockerignore` — ignores local files and build artifacts during Docker builds

## Cloud Run deployment flow

### 1. Build images

Run this from the repository root:

```bash
gcloud builds submit --config cloudbuild.yaml .
```

This creates Docker images:

- `gcr.io/$PROJECT_ID/patentiq-api:$SHORT_SHA`
- `gcr.io/$PROJECT_ID/patentiq-web:$SHORT_SHA`

### 2. Create or connect a Cloud SQL instance

Use PostgreSQL and configure a database, user, and password.

### 3. Deploy the backend to Cloud Run

```bash
gcloud run deploy patentiq-api \
  --image gcr.io/$PROJECT_ID/patentiq-api:$SHORT_SHA \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances="YOUR_PROJECT:REGION:INSTANCE" \
  --set-env-vars="APP_ENV=production,DEBUG=false,DATABASE_URL=postgresql+asyncpg://DB_USER:DB_PASS@/DB_NAME?host=/cloudsql/YOUR_PROJECT:REGION:INSTANCE,CLERK_SECRET_KEY=...,CLERK_JWKS_URL=...,CLERK_ISSUER=...,NEXT_PUBLIC_API_URL=https://YOUR_BACKEND_URL"
```

### 4. Deploy the frontend to Cloud Run

```bash
gcloud run deploy patentiq-web \
  --image gcr.io/$PROJECT_ID/patentiq-web:$SHORT_SHA \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="NEXT_PUBLIC_API_URL=https://YOUR_BACKEND_URL,NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=...,NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in,NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up,NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard,NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard"
```

### 5. Production secrets

Set real values for:

- `DATABASE_URL`
- `CLERK_SECRET_KEY`
- `CLERK_JWKS_URL`
- `CLERK_ISSUER`
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `NEXT_PUBLIC_API_URL`

### 6. Notes

- `vercel.json` is no longer used for GCP deployment.
- `apps/web/src/app/layout.tsx` now passes `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` to `ClerkProvider`.
- `apps/web/next.config.ts` rewrites API routes using `NEXT_PUBLIC_API_URL`.
- Use Cloud SQL `host=/cloudsql/...` via Cloud Run if you connect through the Cloud SQL connector.
