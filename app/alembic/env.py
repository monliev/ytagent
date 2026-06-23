import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# Setup path so alembic can import app modules
this_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(this_dir)
root_dir = os.path.dirname(app_dir)

sys.path.insert(0, app_dir)
sys.path.insert(0, root_dir)

# Load environment variables
load_dotenv(os.path.join(root_dir, ".env"))

# Import target metadata
from app.models.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set database URL dynamically from environment
# Prefer SYNC_DATABASE_URL (explicitly set in docker-compose environment)
# Fall back to building from individual MYSQL_* variables
database_url = os.getenv("SYNC_DATABASE_URL") or (
    "mysql+pymysql://{user}:{pw}@{host}:{port}/{db}".format(
        user=os.getenv("MYSQL_USER", "ytagent"),
        pw=os.getenv("MYSQL_PASSWORD", "ytagent_db_pass_2026"),
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=os.getenv("MYSQL_PORT", "3306"),
        db=os.getenv("MYSQL_DATABASE", "ytagent"),
    )
)
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
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

