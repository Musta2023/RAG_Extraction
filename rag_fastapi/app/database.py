"""
Database management for the RAG pipeline
"""
import databases
import sqlalchemy
from app.config import settings

database = databases.Database(settings.DATABASE_URL)

metadata = sqlalchemy.MetaData()

jobs = sqlalchemy.Table(
    "jobs",
    metadata,
    sqlalchemy.Column("job_id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("data", sqlalchemy.JSON),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, server_default=sqlalchemy.func.now()),
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime, server_default=sqlalchemy.func.now(), onupdate=sqlalchemy.func.now()),
)

documents = sqlalchemy.Table(
    "documents",
    metadata,
    sqlalchemy.Column("doc_id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("job_id", sqlalchemy.String, sqlalchemy.ForeignKey("jobs.job_id")),
    sqlalchemy.Column("url", sqlalchemy.String),
    sqlalchemy.Column("data", sqlalchemy.JSON),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, server_default=sqlalchemy.func.now()),
)

vector_metadata = sqlalchemy.Table(
    "vector_metadata",
    metadata,
    sqlalchemy.Column("chunk_id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("job_id", sqlalchemy.String, sqlalchemy.ForeignKey("jobs.job_id")),
    sqlalchemy.Column("doc_id", sqlalchemy.String, sqlalchemy.ForeignKey("documents.doc_id")),
    sqlalchemy.Column("vector_idx", sqlalchemy.Integer),
    sqlalchemy.Column("data", sqlalchemy.JSON),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, server_default=sqlalchemy.func.now()),
)


async def create_tables():
    """Create database tables"""
    engine = sqlalchemy.create_engine(settings.DATABASE_URL)
    metadata.create_all(engine)

async def connect_db():
    """Connect to the database"""
    await database.connect()

async def disconnect_db():
    """Disconnect from the database"""
    await database.disconnect()
