"""
User configuration management for persistent parameter storage.
Saves configuration to platform-specific user directories.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import platform
import threading
from .utils.logger import setup_logger

logger = setup_logger("user_config")


class UserConfig:
    """Manages user configuration persistence in platform-appropriate directories."""
    
    def __init__(self, app_name: str = "stl_listing_tools"):
        self.app_name = app_name
        self.config_file = "config.json"
        self._config_data = {}
        self._lock = threading.Lock()
        self._config_path = self._get_config_directory()
        self._ensure_config_directory()
        self.load_config()
    
    def _get_config_directory(self) -> Path:
        """Get platform-appropriate config directory."""
        system = platform.system().lower()
        
        if system == "windows":
            # Use APPDATA/Local for Windows (like C:\Users\user\AppData\Local\stl_listing_tools)
            base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
        elif system == "darwin":  # macOS
            # Use ~/Library/Application Support for macOS
            base_dir = os.path.expanduser("~/Library/Application Support")
        else:  # Linux and other Unix-like systems
            # Use XDG_CONFIG_HOME or ~/.config
            base_dir = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        
        config_dir = Path(base_dir) / self.app_name
        logger.info(f"Config directory: {config_dir}")
        return config_dir
    
    def _ensure_config_directory(self):
        """Ensure the config directory exists."""
        try:
            self._config_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Config directory ensured: {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to create config directory {self._config_path}: {e}")
            raise
    
    def get_config_file_path(self) -> Path:
        """Get the full path to the config file."""
        return self._config_path / self.config_file
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        config_file_path = self.get_config_file_path()
        
        with self._lock:
            try:
                if config_file_path.exists():
                    with open(config_file_path, 'r', encoding='utf-8') as f:
                        self._config_data = json.load(f)
                    logger.info(f"Loaded config from {config_file_path}")
                else:
                    self._config_data = {}
                    logger.info("No existing config file, starting with empty config")
            except Exception as e:
                logger.error(f"Failed to load config from {config_file_path}: {e}")
                self._config_data = {}
        
        return self._config_data.copy()
    
    def save_config(self, auto_save: bool = True) -> bool:
        """Save configuration to file."""
        config_file_path = self.get_config_file_path()
        
        with self._lock:
            try:
                with open(config_file_path, 'w', encoding='utf-8') as f:
                    json.dump(self._config_data, f, indent=2, ensure_ascii=False)
                
                if not auto_save:  # Only log manual saves to avoid spam
                    logger.info(f"Config saved to {config_file_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to save config to {config_file_path}: {e}")
                return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        with self._lock:
            return self._config_data.get(key, default)
    
    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        """Set a configuration value and optionally auto-save."""
        with self._lock:
            self._config_data[key] = value
        
        if auto_save:
            self.save_config(auto_save=True)
    
    def update(self, updates: Dict[str, Any], auto_save: bool = True) -> None:
        """Update multiple configuration values."""
        with self._lock:
            self._config_data.update(updates)
        
        if auto_save:
            self.save_config(auto_save=True)
    
    def remove(self, key: str, auto_save: bool = True) -> None:
        """Remove a configuration value."""
        with self._lock:
            if key in self._config_data:
                del self._config_data[key]
        
        if auto_save:
            self.save_config(auto_save=True)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        with self._lock:
            return self._config_data.copy()
    
    def clear(self, auto_save: bool = True) -> None:
        """Clear all configuration values."""
        with self._lock:
            self._config_data.clear()
        
        if auto_save:
            self.save_config(auto_save=True)


# Global user config instance
user_config = UserConfig()


def get_user_config() -> UserConfig:
    """Get the global user configuration instance."""
    return user_config