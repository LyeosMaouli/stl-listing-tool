from pydantic import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Paths
    INPUT_DIR: str = "./data/input"
    OUTPUT_DIR: str = "./data/output" 
    TEMP_DIR: str = "./data/temp"
    
    # Processing
    MAX_WORKERS: int = 4
    BATCH_SIZE: int = 10
    CHECKPOINT_INTERVAL: int = 5
    
    # Rendering
    RENDER_WIDTH: int = 1920
    RENDER_HEIGHT: int = 1080
    SAMPLES: int = 128
    
    # Queue
    REDIS_URL: str = "redis://localhost:6379"
    JOB_TIMEOUT: int = 3600
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/stl_processor.log"
    
    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()