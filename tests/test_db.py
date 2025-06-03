# test_db_connection.py
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Get database connection parameters
db_user = os.environ.get('DB_USER', 'app_remote')
db_password = os.environ.get('DB_PASSWORD', 'plmnko1423$')
db_name = os.environ.get('DB_NAME', 'replify')

# Create connection string
db_uri = f'postgresql://{db_user}:{db_password}@192.46.222.246:5432/{db_name}'

print(f"Attempting to connect to: {db_uri}")

try:
    # Create engine and connect
    engine = create_engine(db_uri)
    with engine.connect() as connection:
        # Test with a simple query
        result = connection.execute(text('SELECT 1 as test'))
        first_row = result.fetchone()
        print(f"Database connection successful! Result: {first_row.test}")
except Exception as e:
    print(f"Error connecting to database: {str(e)}")