from typing import Optional, AsyncGenerator
from sqlmodel import SQLModel, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import Field as SQLField

# Database configuration
DATABASE_URL = "postgresql+asyncpg://user:password@localhost/dbname"

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=True, future=True)

# Create async session
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Base model for SQLModel
class SQLModelBase(SQLModel):
    id: Optional[int] = SQLField(default=None, primary_key=True)


# Function to initialize the database
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


# Dependency to get DB session
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
