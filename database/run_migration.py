"""Run the initial SQL migration against Neon PostgreSQL."""
import psycopg2
import ssl

DATABASE_URL = "postgresql://neondb_owner:npg_HEi1bZ7MLkcV@ep-dark-feather-am2o5qga.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require"

def run_migration():
    print("Connecting to Neon...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Reading migration file...")
    with open(r"d:\box mation\database\migrations\001_initial_schema.sql", "r") as f:
        sql = f.read()
    
    print("Running migration...")
    cur.execute(sql)
    print("Migration complete!")
    
    # Verify tables
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]
    print(f"\nCreated {len(tables)} tables:")
    for t in tables:
        print(f"  - {t}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    run_migration()
