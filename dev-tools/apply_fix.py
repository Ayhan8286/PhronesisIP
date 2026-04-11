
import psycopg2
import os
from dotenv import load_dotenv

# Path to the API's .env file
API_ENV_PATH = r"d:\box mation\apps\api\.env"
MIGRATION_SQL_PATH = r"d:\box mation\database\migrations\003_safe_rls.sql"

def apply_fix():
    print(f"Loading environment from {API_ENV_PATH}...")
    load_dotenv(API_ENV_PATH)
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not found in .env")
        return

    # psycopg2 needs postgres:// not postgresql+asyncpg://
    # And it wants 'sslmode' instead of 'ssl'
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if "ssl=" in db_url:
        db_url = db_url.replace("ssl=", "sslmode=", 1)
    elif "sslmode" not in db_url:
        if "?" in db_url:
            db_url += "&sslmode=require"
        else:
            db_url += "?sslmode=require"

    print("Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        print(f"Reading migration file {MIGRATION_SQL_PATH}...")
        with open(MIGRATION_SQL_PATH, "r") as f:
            sql = f.read()
        
        print("Applying migration...")
        cur.execute(sql)
        print("Migration applied successfully!")
        
        # Verify columns in patents
        print("\nVerifying columns in 'patents' table:")
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'patents'")
        columns = [row[0] for row in cur.fetchall()]
        print(f"Columns: {', '.join(columns)}")
        
        if 'deleted_at' in columns:
            print("SUCCESS: 'deleted_at' found in 'patents'.")
        else:
            print("FAILURE: 'deleted_at' NOT found in 'patents'.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error applying migration: {str(e)}")

if __name__ == "__main__":
    apply_fix()
