from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker 
# from dotenv import load_dotenv
# import os

# load_dotenv()

# DATABASE_URL = os.getenv("DATABASE_URL")

# if not DATABASE_URL:
#     POSTGRES_USER = os.getenv('PG_USER')
#     POSTGRES_PASSWORD = os.getenv('PG_PASSWORD')
#     POSTGRES_HOST = os.getenv('PG_HOST')
#     POSTGRES_PORT = os.getenv('PG_PORT')
#     POSTGRES_DB = os.getenv('PG_DB')

#     DATABASE_URL = f"postgreql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
DATABASE_URL = 'postgresql://patz:root@localhost/maladb'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()