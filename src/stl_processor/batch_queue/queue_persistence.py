"""
Queue state persistence system.

This module handles saving and loading queue state to/from JSON files,
with atomic operations, backup management, and error recovery.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading
import uuid

from ..utils.logger import setup_logger
from .job_types import QueueJob, JobState, RenderOptions, ValidationOptions, AnalysisOptions

logger = setup_logger("queue.persistence")


class QueueStateManager:
    """
    Manages persistent storage of queue state with backup and recovery.
    
    Provides atomic save operations, automatic backups, and corruption recovery
    to ensure queue state is never lost.
    """
    
    def __init__(self, state_file: Optional[Path] = None, max_backups: int = 5):
        """
        Initialize queue state manager.
        
        Args:
            state_file: Path to state file (default: ~/.local/stl_listing_tool/queue_state.json)
            max_backups: Maximum number of backup files to keep
        """
        if state_file is None:
            # Default location
            config_dir = Path.home() / ".local" / "stl_listing_tool"
            config_dir.mkdir(parents=True, exist_ok=True)
            state_file = config_dir / "queue_state.json"
        
        self.state_file = state_file
        self.backup_dir = self.state_file.parent / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.max_backups = max_backups
        
        self._lock = threading.Lock()
        
        logger.info(f"Queue state manager initialized: {self.state_file}")
    
    def save_queue_state(self, jobs: List[QueueJob], metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save queue state to file with atomic operation and backup.
        
        Args:
            jobs: List of jobs to save
            metadata: Optional metadata to include in state file
            
        Returns:
            bool: True if save was successful
        """
        with self._lock:
            try:
                # Create backup before saving new state
                backup_path = self._create_backup()
                
                # Prepare state data
                state_data = {
                    "version": "1.0",
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "metadata": metadata or {},
                    "jobs": [job.to_dict() for job in jobs]
                }
                
                # Write to temporary file first (atomic operation)
                temp_file = self.state_file.with_suffix('.tmp')
                
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(state_data, f, indent=2, ensure_ascii=False)
                
                # Atomic rename to final location
                temp_file.replace(self.state_file)
                
                # Clean up old backups
                self._cleanup_old_backups()
                
                logger.info(f"Saved queue state with {len(jobs)} jobs")
                return True
                
            except Exception as e:
                logger.error(f"Failed to save queue state: {e}")
                
                # Restore from backup if we have one
                if backup_path and backup_path.exists():
                    try:
                        backup_path.replace(self.state_file)
                        logger.info("Restored from backup after save failure")
                    except Exception as restore_error:
                        logger.error(f"Failed to restore from backup: {restore_error}")
                
                return False
            finally:
                # Clean up temp file if it exists
                temp_file = self.state_file.with_suffix('.tmp')
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except:
                        pass
    
    def load_queue_state(self) -> Optional[Dict[str, Any]]:
        """
        Load queue state from file with error recovery.
        
        Returns:
            Dict containing state data, or None if load failed
        """
        with self._lock:
            if not self.state_file.exists():
                logger.info("No existing queue state file found")
                return None
            
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                
                # Validate state data structure
                if not self._validate_state_data(state_data):
                    logger.error("Invalid state data structure")
                    return self._attempt_recovery()
                
                logger.info(f"Loaded queue state with {len(state_data.get('jobs', []))} jobs")
                return state_data
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in state file: {e}")
                return self._attempt_recovery()
            
            except Exception as e:
                logger.error(f"Failed to load queue state: {e}")
                return self._attempt_recovery()
    
    def load_jobs_from_state(self, state_data: Dict[str, Any]) -> List[QueueJob]:
        """
        Convert state data to list of QueueJob objects.
        
        Args:
            state_data: State data from load_queue_state()
            
        Returns:
            List of reconstructed QueueJob objects
        """
        jobs = []
        job_data_list = state_data.get('jobs', [])
        
        for job_data in job_data_list:
            try:
                # Validate job data
                if not isinstance(job_data, dict) or 'id' not in job_data:
                    logger.warning(f"Skipping invalid job data: {job_data}")
                    continue
                
                # Reconstruct job
                job = QueueJob.from_dict(job_data)
                jobs.append(job)
                
            except Exception as e:
                logger.error(f"Failed to reconstruct job {job_data.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"Successfully reconstructed {len(jobs)} jobs from state")
        return jobs
    
    def migrate_state_version(self, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate state data between versions.
        
        Args:
            state_data: State data to migrate
            
        Returns:
            Migrated state data
        """
        version = state_data.get('version', '1.0')
        
        if version == '1.0':
            # Current version, no migration needed
            return state_data
        
        # Future migrations would go here
        logger.warning(f"Unknown state version: {version}, attempting to use as-is")
        return state_data
    
    def get_backup_files(self) -> List[Path]:
        """Get list of available backup files, sorted by creation time."""
        if not self.backup_dir.exists():
            return []
        
        backups = list(self.backup_dir.glob("queue_state_backup_*.json"))
        # Sort by modification time (newest first)
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        return backups
    
    def restore_from_backup(self, backup_file: Optional[Path] = None) -> bool:
        """
        Restore queue state from backup file.
        
        Args:
            backup_file: Specific backup file to restore from (None = most recent)
            
        Returns:
            bool: True if restore was successful
        """
        with self._lock:
            try:
                if backup_file is None:
                    # Use most recent backup
                    backups = self.get_backup_files()
                    if not backups:
                        logger.error("No backup files available")
                        return False
                    backup_file = backups[0]
                
                if not backup_file.exists():
                    logger.error(f"Backup file does not exist: {backup_file}")
                    return False
                
                # Validate backup file
                with open(backup_file, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
                
                if not self._validate_state_data(backup_data):
                    logger.error("Invalid backup file structure")
                    return False
                
                # Copy backup to main state file
                shutil.copy2(backup_file, self.state_file)
                
                logger.info(f"Restored queue state from backup: {backup_file}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to restore from backup: {e}")
                return False
    
    def _create_backup(self) -> Optional[Path]:
        """Create backup of current state file."""
        if not self.state_file.exists():
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"queue_state_backup_{timestamp}_{uuid.uuid4().hex[:8]}.json"
            backup_path = self.backup_dir / backup_name
            
            shutil.copy2(self.state_file, backup_path)
            logger.debug(f"Created backup: {backup_path}")
            
            return backup_path
            
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
            return None
    
    def _cleanup_old_backups(self):
        """Remove old backup files to limit storage usage."""
        try:
            backups = self.get_backup_files()
            
            # Remove excess backups (keep only max_backups newest)
            if len(backups) > self.max_backups:
                for old_backup in backups[self.max_backups:]:
                    try:
                        old_backup.unlink()
                        logger.debug(f"Removed old backup: {old_backup}")
                    except Exception as e:
                        logger.warning(f"Failed to remove old backup {old_backup}: {e}")
            
        except Exception as e:
            logger.warning(f"Error cleaning up old backups: {e}")
    
    def _validate_state_data(self, state_data: Dict[str, Any]) -> bool:
        """Validate state data structure."""
        if not isinstance(state_data, dict):
            return False
        
        required_keys = ['version', 'jobs']
        if not all(key in state_data for key in required_keys):
            return False
        
        if not isinstance(state_data['jobs'], list):
            return False
        
        return True
    
    def _attempt_recovery(self) -> Optional[Dict[str, Any]]:
        """Attempt to recover from corrupted state file using backups."""
        logger.info("Attempting recovery from backup files")
        
        backups = self.get_backup_files()
        
        for backup_file in backups:
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
                
                if self._validate_state_data(backup_data):
                    logger.info(f"Successfully recovered from backup: {backup_file}")
                    return backup_data
                
            except Exception as e:
                logger.warning(f"Backup file {backup_file} also corrupted: {e}")
                continue
        
        logger.error("All recovery attempts failed")
        return None


class QueueConfiguration:
    """
    Manages queue configuration templates and settings.
    
    Provides functionality to save, load, and manage reusable queue
    configuration templates for different processing scenarios.
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize configuration manager."""
        if config_dir is None:
            config_dir = Path.home() / ".local" / "stl_listing_tool" / "templates"
        
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Queue configuration manager initialized: {self.config_dir}")
    
    def save_template(self, name: str, template_data: Dict[str, Any]) -> bool:
        """
        Save a queue configuration template.
        
        Args:
            name: Template name
            template_data: Template configuration data
            
        Returns:
            bool: True if save was successful
        """
        try:
            template_file = self.config_dir / f"{name}.json"
            
            template_data = {
                **template_data,
                'created_at': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved template: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save template {name}: {e}")
            return False
    
    def load_template(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Load a queue configuration template.
        
        Args:
            name: Template name to load
            
        Returns:
            Template data or None if load failed
        """
        try:
            template_file = self.config_dir / f"{name}.json"
            
            if not template_file.exists():
                logger.warning(f"Template not found: {name}")
                return None
            
            with open(template_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            logger.info(f"Loaded template: {name}")
            return template_data
            
        except Exception as e:
            logger.error(f"Failed to load template {name}: {e}")
            return None
    
    def list_templates(self) -> List[str]:
        """Get list of available template names."""
        try:
            templates = []
            for template_file in self.config_dir.glob("*.json"):
                templates.append(template_file.stem)
            
            return sorted(templates)
            
        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
            return []
    
    def delete_template(self, name: str) -> bool:
        """Delete a template."""
        try:
            template_file = self.config_dir / f"{name}.json"
            
            if template_file.exists():
                template_file.unlink()
                logger.info(f"Deleted template: {name}")
                return True
            else:
                logger.warning(f"Template not found: {name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete template {name}: {e}")
            return False
    
    def create_default_templates(self):
        """Create default configuration templates."""
        templates = {
            "quick_preview": {
                "name": "Quick Preview",
                "description": "Fast preview renders for quick inspection",
                "render_options": {
                    "generate_image": True,
                    "generate_size_chart": False,
                    "generate_video": False,
                    "generate_color_variations": False,
                    "width": 1280,
                    "height": 720,
                    "material": "plastic",
                    "lighting": "studio",
                    "quality": "draft"
                },
                "validation_options": {
                    "level": "basic",
                    "auto_repair": True,
                    "generate_report": False
                }
            },
            
            "complete_processing": {
                "name": "Complete Processing",
                "description": "Full processing with all output types",
                "render_options": {
                    "generate_image": True,
                    "generate_size_chart": True,
                    "generate_video": True,
                    "generate_color_variations": True,
                    "width": 1920,
                    "height": 1080,
                    "material": "plastic",
                    "lighting": "studio",
                    "quality": "standard"
                },
                "validation_options": {
                    "level": "standard",
                    "auto_repair": True,
                    "generate_report": True
                },
                "analysis_options": {
                    "generate_report": True,
                    "report_format": "json",
                    "include_dimensions": True,
                    "include_printability": True,
                    "include_mesh_quality": True
                }
            },
            
            "validation_only": {
                "name": "Validation Only", 
                "description": "Validate and repair meshes without rendering",
                "validation_options": {
                    "level": "strict",
                    "auto_repair": True,
                    "generate_report": True
                }
            },
            
            "high_quality_renders": {
                "name": "High Quality Renders",
                "description": "Premium quality renders with videos",
                "render_options": {
                    "generate_image": True,
                    "generate_size_chart": True,
                    "generate_video": True,
                    "generate_color_variations": False,
                    "width": 3840,
                    "height": 2160,
                    "material": "plastic",
                    "lighting": "studio",
                    "quality": "high"
                },
                "validation_options": {
                    "level": "standard",
                    "auto_repair": True,
                    "generate_report": False
                }
            }
        }
        
        for name, template_data in templates.items():
            if not (self.config_dir / f"{name}.json").exists():
                self.save_template(name, template_data)
                logger.info(f"Created default template: {name}")


# Convenience functions
def save_queue_to_file(jobs: List[QueueJob], state_file: Optional[Path] = None, 
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Save queue jobs to file."""
    manager = QueueStateManager(state_file)
    return manager.save_queue_state(jobs, metadata)


def load_queue_from_file(state_file: Optional[Path] = None) -> List[QueueJob]:
    """Load queue jobs from file."""
    manager = QueueStateManager(state_file)
    state_data = manager.load_queue_state()
    
    if state_data is None:
        return []
    
    return manager.load_jobs_from_state(state_data)


def get_queue_state_manager(state_file: Optional[Path] = None) -> QueueStateManager:
    """Get queue state manager instance."""
    return QueueStateManager(state_file)