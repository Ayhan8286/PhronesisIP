# Fly.io Backend Deployment for PatentIQ

This repository now supports deploying the FastAPI backend to Fly.io while keeping the frontend on Vercel.

## Backend location
- `apps/api` contains the FastAPI backend
- `apps/api/Dockerfile` builds the backend image
- `apps/api/fly.toml` configures Fly.io for the backend

## Backend deployment steps

1. Install Fly CLI:
```bash
curl -L https://fly.io/install.sh | sh
```

2. Log in:
```bash
fly auth login
```

3. From the backend folder:
```bash
cd apps/api
./deploy_fly.sh
```

If you are on Windows PowerShell:
```powershell
cd apps/api
.\deploy_fly.ps1
```

4. Set required secrets on Fly:
```bash
fly secrets set \
  DATABASE_URL="postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DB_NAME" \
  CLERK_SECRET_KEY="..." \
  CLERK_JWKS_URL="https://<your-clerk-domain>/.well-known/jwks.json" \
  CLERK_ISSUER="https://<your-clerk-domain>" \
  REDIS_URL="redis://..."
```

5. Configure the frontend Vercel project to use the Fly backend URL:
- `NEXT_PUBLIC_API_URL=https://<your-fly-app>.fly.dev`

## Notes
- Frontend remains on Vercel and uses `NEXT_PUBLIC_API_URL` to call the Fly.io backend.
- `apps/web/next.config.ts` already rewrites `/api/v1/*` and `/api/inngest` to `NEXT_PUBLIC_API_URL`.
- Keep the frontend URL as the Vercel domain and backend URL as Fly domain.
