from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", 'postgresql+psycopg2://patz:root@164.90.185.12:5432/maladb')

# Configure the engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,  # Maximum number of connections to keep persistently
    max_overflow=10,  # Maximum number of connections that can be created above pool_size
    pool_timeout=30,  # Timeout for getting a connection from the pool
    pool_pre_ping=True,  # Enable connection health checks
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False  # Set to True for SQL query logging
)

# Optimize connection handling
@event.listens_for(engine, "connect")
def optimize_postgres_connection(dbapi_connection, connection_record):
    # Disable autocommit to enable more efficient transaction handling
    dbapi_connection.autocommit = False
    cursor = dbapi_connection.cursor()
    # Set session parameters for better performance
    cursor.execute("SET timezone='UTC';")
    cursor.execute("SET statement_timeout = '30s';")  # Prevent long-running queries
    cursor.execute("SET idle_in_transaction_session_timeout = '60s';")  # Clear idle sessions
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
