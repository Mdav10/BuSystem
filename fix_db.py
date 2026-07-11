import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

# Connect to database
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Check if full_name column exists
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='full_name';")
result = cur.fetchone()

if result:
    print("Dropping full_name column...")
    cur.execute("ALTER TABLE users DROP COLUMN full_name;")
    conn.commit()
    print("✅ Column dropped successfully!")

# Check if email column exists
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='email';")
result = cur.fetchone()

if not result:
    print("Adding email column...")
    cur.execute("ALTER TABLE users ADD COLUMN email VARCHAR(120);")
    conn.commit()
    print("✅ Email column added!")

# Make sure MCM user exists
cur.execute("SELECT username FROM users WHERE username='MCM';")
result = cur.fetchone()

if not result:
    print("Creating MCM user...")
    from werkzeug.security import generate_password_hash
    password_hash = generate_password_hash('0880Mcm+_+')
    cur.execute("INSERT INTO users (username, password_hash, currency) VALUES ('MCM', %s, 'FCFA');", (password_hash,))
    conn.commit()
    print("✅ User MCM created!")

cur.close()
conn.close()
print("🎉 Database fixed successfully!")
