# Open-Source + Grok Stack

This repo can be run with Grok as the only paid AI dependency.

## Recommended setup

- Frontend: Vercel free tier or Cloudflare Pages
- Backend: local machine, Fly.io, or any small container host
- Database: Neon free Postgres or Supabase free Postgres with `pgvector`
- Storage: Cloudflare R2 if you need document uploads, otherwise local disk for development
- Cache: optional local Redis; disable external Redis for development if needed
- LLM: xAI Grok via `XAI_API_KEY`
- Embeddings: local open-source `BAAI/bge-m3`

## Why this fits the current codebase

- Your vector schema is already `1024` dimensions, which matches `BAAI/bge-m3`.
- The backend uses `pgvector`, so Neon or Supabase remain low-friction choices.
- Grok is available through an OpenAI-compatible base URL at `https://api.x.ai/v1`.

## Minimal env

```env
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/patentiq

LLM_PROVIDER=xai
LLM_MODEL=grok-4.20-reasoning
XAI_API_KEY=your_xai_key
XAI_BASE_URL=https://api.x.ai/v1

EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
EMBEDDING_QUERY_PREFIX=Represent this sentence for searching relevant passages:
```

## Notes

- Local embeddings reduce recurring cost but increase RAM/CPU usage on the backend host.
- If you deploy to a tiny serverless runtime, local embeddings may be too heavy; in that case use Jina temporarily or move embeddings to a separate worker.
- If you keep `apps/api/app/.env` in version control, rotate those secrets immediately and remove real keys from the repo.
