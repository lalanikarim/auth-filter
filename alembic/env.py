import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from app.db import Base
from app import models  # Ensure all models are registered with Base.metadata

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Use DATABASE_URL environment variable if available
    url = os.getenv("DATABASE_URL")
    
    # If DATABASE_URL is not set, try to construct it from individual env vars
    if not url:
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST", "127.0.0.1")
        db_port = os.getenv("DB_PORT", "3306")
        db_name = os.getenv("DB_NAME")
        
        if all([db_user, db_password, db_name]):
            # URL encode the password to handle special characters
            import urllib.parse
            encoded_password = urllib.parse.quote_plus(db_password)
            url = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
    
    # Convert async URLs to sync URLs for Alembic
    if url and url.startswith("mysql+aiomysql://"):
        url = url.replace("mysql+aiomysql://", "mysql+pymysql://")
    
    # Fall back to config if no environment variables are set
    if not url:
        url = config.get_main_option("sqlalchemy.url") or config.attributes.get('sqlalchemy.url')
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Use DATABASE_URL environment variable if available
    database_url = os.getenv("DATABASE_URL")
    
    # If DATABASE_URL is not set, try to construct it from individual env vars
    if not database_url:
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST", "127.0.0.1")
        db_port = os.getenv("DB_PORT", "3306")
        db_name = os.getenv("DB_NAME")
        
        if all([db_user, db_password, db_name]):
            # URL encode the password to handle special characters
            import urllib.parse
            encoded_password = urllib.parse.quote_plus(db_password)
            database_url = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
    
    # Convert async URLs to sync URLs for Alembic
    if database_url and database_url.startswith("mysql+aiomysql://"):
        database_url = database_url.replace("mysql+aiomysql://", "mysql+pymysql://")
    
    if database_url:
        # Override the sqlalchemy.url in the config
        # Use a different approach to avoid interpolation issues
        config.attributes['sqlalchemy.url'] = database_url
    
    config_dict = config.get_section(config.config_ini_section, {})
    config_dict['sqlalchemy.url'] = database_url
    connectable = engine_from_config(
        config_dict,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
