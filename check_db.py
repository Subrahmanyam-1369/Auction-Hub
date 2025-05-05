import os
from dotenv import load_dotenv
import mysql.connector

# Load environment variables
load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', 'password'),
        database=os.getenv('MYSQL_DB', 'auctionhub')
    )

def check_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check tables
        cursor.execute('SHOW TABLES')
        tables = cursor.fetchall()
        print("Tables in database:")
        for table in tables:
            print(f"- {list(table.values())[0]}")
        
        # Check categories
        cursor.execute('SELECT COUNT(*) as count FROM categories')
        result = cursor.fetchone()
        print(f"\nCategories count: {result['count'] if result else 0}")
        
        if result and result['count'] > 0:
            cursor.execute('SELECT * FROM categories')
            categories = cursor.fetchall()
            print("\nCategories:")
            for category in categories:
                print(f"- {category['id']}: {category['name']}")
        else:
            print("\nNo categories found. Adding some default categories...")
            # Insert some default categories
            default_categories = ["Electronics", "Real Estate", "Vehicles", "Art", "Jewelry", "Furniture"]
            for category in default_categories:
                try:
                    cursor.execute('INSERT INTO categories (name) VALUES (%s)', (category,))
                    print(f"Added category: {category}")
                except Exception as e:
                    print(f"Error adding category {category}: {str(e)}")
            
            conn.commit()
        
        cursor.close()
        conn.close()
        print("\nDatabase check completed.")
    except Exception as e:
        print(f"Error checking database: {str(e)}")

if __name__ == "__main__":
    check_database() 