from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Get username, password and dbname from environment variables using dotenv
import os
from dotenv import load_dotenv
load_dotenv()
# Load environment variables
username = os.getenv('DB_USERNAME')
password = os.getenv('DB_PASSWORD')
db_name = os.getenv('DB_NAME')
db_host = os.getenv('DB_HOST', 'localhost')

if username is None or password is None or db_name is None:
    raise ValueError("Database credentials are not set in the environment variables.")


DATABASE_URL = f"postgresql://{username}:{password}@{db_host}:5432/{db_name}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
