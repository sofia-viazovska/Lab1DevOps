from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import yaml
import os

# Priority: 1. Environment variable 2. Global config 3. Local config
config_path = os.getenv("APP_CONFIG_PATH", "/etc/mywebapp/config.yaml")
if not os.path.exists(config_path):
    # Search relative to project root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_config = os.path.join(base_dir, "config.yaml")
    subdir_config = os.path.join(base_dir, "config", "config.yaml")
    
    if os.path.exists(local_config):
        config_path = local_config
    elif os.path.exists(subdir_config):
        config_path = subdir_config

if os.path.exists(config_path):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    database_url = config['database_url']
else:
    # Fallback to env var if config file not found
    database_url = os.getenv("DATABASE_URL", "sqlite:///./test.db")
    if "sqlite" in database_url:
        print(f"Warning: Config file not found at {config_path}. Falling back to sqlite.")

engine = create_engine(database_url, connect_args={"check_same_thread": False} if "sqlite" in database_url else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()