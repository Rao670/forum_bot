import sqlite3
import os

db_path = 'bot_data.db'

def check_db():
    if not os.path.exists(db_path):
        print(f"FAILED: {db_path} not found.")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check schema
        print("Table Schema:")
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='interactions';")
        print(cursor.fetchone()[0])
        print("-" * 50)
        
        # Check unity post specifically
        post_id = '1697328'
        print(f"Checking for Post ID: {post_id}")
        cursor.execute("SELECT * FROM interactions WHERE post_id=?", (post_id,))
        rows = cursor.fetchall()
        
        if rows:
            print(f"SUCCESS: Found {len(rows)} record(s) in local database!")
            for row in rows:
                print(row)
        else:
            print("FAILED: No records found for this Post ID in local database.")
            
        print("\nLast 5 interactions:")
        cursor.execute("SELECT * FROM interactions ORDER BY timestamp DESC LIMIT 5")
        for row in cursor.fetchall():
            print(row)
            
        conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    check_db()
