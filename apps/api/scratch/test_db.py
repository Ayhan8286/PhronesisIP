
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

async def test_connection():
    # Load .env from the app directory
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    print(f"Loading env from: {os.path.abspath(env_path)}")
    load_dotenv(env_path)
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in .env")
        return

    # Fix URL if needed (same logic as in config.py)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print(f"Testing connection to: {db_url}")
    
    try:
        engine = create_async_engine(db_url, echo=True)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version();"))
            row = result.fetchone()
            print(f"Connection successful! PostgreSQL version: {row[0]}")
    except Exception as e:
        print(f"Connection failed: {type(e).__name__}: {str(e)}")
    finally:
        if 'engine' in locals():
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_connection())
