from pydantic import BaseModel, Field
from pathlib import Path


class Settings(BaseModel):
    # Paths
    INPUT_DIR: str = Field(default="./data/input", description="Input directory for STL files")
    OUTPUT_DIR: str = Field(default="./data/output", description="Output directory for processed files")
    TEMP_DIR: str = Field(default="./data/temp", description="Temporary directory for processing")
    
    # Processing
    MAX_WORKERS: int = Field(default=4, ge=1, le=16, description="Maximum number of worker processes")
    BATCH_SIZE: int = Field(default=10, ge=1, le=100, description="Batch size for processing")
    CHECKPOINT_INTERVAL: int = Field(default=5, ge=1, description="Checkpoint interval in minutes")
    
    # Rendering
    RENDER_WIDTH: int = Field(default=1920, ge=100, le=4096, description="Default render width in pixels")
    RENDER_HEIGHT: int = Field(default=1080, ge=100, le=4096, description="Default render height in pixels")
    SAMPLES: int = Field(default=128, ge=16, le=1024, description="Render samples for quality")
    
    # Queue
    REDIS_URL: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    JOB_TIMEOUT: int = Field(default=3600, ge=60, description="Job timeout in seconds")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FILE: str = Field(default="./logs/stl_processor.log", description="Log file path")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "validate_assignment": True,
    }


# Global settings instance
settings = Settings()