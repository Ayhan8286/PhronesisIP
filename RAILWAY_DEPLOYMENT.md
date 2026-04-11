# Railway Backend Deployment for PatentIQ

This guide explains how to deploy the FastAPI backend to Railway while keeping the frontend on Vercel.

## 1. Prepare your Repository
Ensure your latest changes are pushed to GitHub. Railway will deploy directly from your source code.

## 2. Create a Railway Service
1. Log in to [Railway](https://railway.app/).
2. Click **"New Project"** -> **"Deploy from GitHub repo"**.
3. Select your repository: `Ayhan8286/PhronesisIP`.
4. **IMPORTANT**: When the service is created, go to the **"Settings"** tab of the newly created service.
5. Under **"General"**, find **"Root Directory"** and set it to: `apps/api`.
    - This tells Railway to build and run only the backend service.

## 3. Set Environment Variables
Go to the **"Variables"** tab in Railway and add the following from your `.env` file:

- `DATABASE_URL` (Neon PostgreSQL)
- `CLERK_SECRET_KEY`
- `CLERK_JWKS_URL`
- `CLERK_ISSUER`
- `VOYAGE_API_KEY`
- `GOOGLE_API_KEY`
- `EPO_CLIENT_ID`
- `EPO_CLIENT_SECRET`
- `SENTRY_DSN`
- `REDIS_URL` (if applicable)

## 4. Connect Frontend (Vercel)
Once the Railway service is deployed:
1. Copy your Railway app URL (e.g., `https://your-app-name.up.railway.app`).
2. Go to your **Vercel Dashboard**.
3. Add or update the Environment Variable:
   - `NEXT_PUBLIC_API_URL`: Your Railway App URL.
4. Redeploy your frontend.

## 5. Verify Deployment
Visit your Railway URL at:
`https://your-app-name.up.railway.app/api/v1/health`

It should return:
```json
{"status":"healthy","service":"patentiq-api",...}
```
