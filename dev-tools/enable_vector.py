import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Using the database URL from the .env check earlier
DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_HEi1bZ7MLkcV@ep-dark-feather-am2o5qga.c-5.us-east-1.aws.neon.tech/neondb?ssl=require"

async def enable_vector():
    print(f"Connecting to {DATABASE_URL.split('@')[1]}...")
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        print("Enabling pgvector extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        print("Success! pgvector is now enabled.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(enable_vector())
