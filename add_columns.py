import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    
    # Check if currency column exists
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='currency'
    """)
    
    if not cur.fetchone():
        print("Adding currency column...")
        cur.execute("ALTER TABLE users ADD COLUMN currency VARCHAR(10) DEFAULT 'FCFA';")
        conn.commit()
        print("✅ currency column added")
    else:
        print("✅ currency column already exists")
    
    # Check if email column exists
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='email'
    """)
    
    if not cur.fetchone():
        print("Adding email column...")
        cur.execute("ALTER TABLE users ADD COLUMN email VARCHAR(120);")
        conn.commit()
        print("✅ email column added")
    else:
        print("✅ email column already exists")
    
    # Check if full_name column exists (just in case)
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='full_name'
    """)
    
    if cur.fetchone():
        print("Removing full_name column...")
        cur.execute("ALTER TABLE users DROP COLUMN full_name;")
        conn.commit()
        print("✅ full_name column removed")
    
    cur.close()
    conn.close()
    print("🎉 Database schema updated successfully!")
    
except Exception as e:
    print(f"Error: {e}")
