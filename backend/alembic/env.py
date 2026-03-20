import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent.parent
backend = Path(__file__).resolve().parent.parent
sys.path.append(str(root))
sys.path.append(str(backend))

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Import your models here
from app.core.config import settings
from app.db.base import Base
from shared.models.user import User, Strategy, Order
from shared.models.news import News
from shared.models.signal import Signal
from shared.models.system import SystemConfig
from shared.models.workflow import WorkflowSession, AgentLog, WorkflowStatus
from app.services.paper_trading import PaperAccount, PaperOrder, PaperPosition, SessionReflection
# Ensure all models are imported so Base.metadata knows about them

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_USER_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_USER_URL
    
    connectable = engine_from_config(
        configuration,
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
