"""
File scanner for discovering STL files in directories.

This module provides functionality to recursively scan directories for STL files,
with filtering options, progress reporting, and validation capabilities.
"""

import os
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Callable, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
import threading

from utils.logger import setup_logger

logger = setup_logger("queue.file_scanner")


@dataclass
class FileInfo:
    """Information about a discovered STL file."""
    path: Path
    size: int
    modified_time: datetime
    checksum: Optional[str] = None
    is_valid: Optional[bool] = None
    validation_error: Optional[str] = None


@dataclass
class ScanResult:
    """Results from a directory scan operation."""
    files_found: List[FileInfo]
    directories_scanned: int
    total_files_checked: int
    scan_duration: float
    errors: List[str]
    
    @property
    def valid_files(self) -> List[FileInfo]:
        """Get only valid STL files."""
        return [f for f in self.files_found if f.is_valid is not False]
    
    @property
    def invalid_files(self) -> List[FileInfo]:
        """Get only invalid STL files.""" 
        return [f for f in self.files_found if f.is_valid is False]


class FileScanner:
    """
    Scanner for discovering and validating STL files in directories.
    
    Supports recursive scanning, file validation, progress reporting,
    and filtering options.
    """
    
    def __init__(self):
        self._cancel_requested = False
        self._lock = threading.Lock()
        
    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
        validate_files: bool = False,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> ScanResult:
        """
        Scan directory for STL files.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            validate_files: Whether to validate STL files during scan
            include_patterns: File patterns to include (e.g., ['*.stl'])
            exclude_patterns: File patterns to exclude (e.g., ['*temp*'])
            progress_callback: Optional callback(files_found, total_checked, current_file)
            
        Returns:
            ScanResult: Results of the scan operation
        """
        start_time = datetime.now()
        self._cancel_requested = False
        
        if not directory.exists():
            logger.error(f"Directory does not exist: {directory}")
            return ScanResult([], 0, 0, 0.0, [f"Directory does not exist: {directory}"])
        
        if not directory.is_dir():
            logger.error(f"Path is not a directory: {directory}")
            return ScanResult([], 0, 0, 0.0, [f"Path is not a directory: {directory}"])
        
        logger.info(f"Starting scan of {directory} (recursive={recursive})")
        
        files_found: List[FileInfo] = []
        directories_scanned = 0
        total_files_checked = 0
        errors: List[str] = []
        
        try:
            # Default patterns
            if include_patterns is None:
                include_patterns = ['*.stl', '*.STL']
            if exclude_patterns is None:
                exclude_patterns = []
            
            # Walk directory tree
            if recursive:
                iterator = os.walk(directory)
            else:
                # Only scan the top-level directory
                iterator = [(directory, [], [f for f in os.listdir(directory) 
                                          if (directory / f).is_file()])]
            
            for root, dirs, files in iterator:
                if self._cancel_requested:
                    logger.info("Scan cancelled by user")
                    break
                
                root_path = Path(root)
                directories_scanned += 1
                
                for filename in files:
                    if self._cancel_requested:
                        break
                    
                    total_files_checked += 1
                    file_path = root_path / filename
                    
                    # Report progress
                    if progress_callback:
                        try:
                            progress_callback(len(files_found), total_files_checked, str(file_path))
                        except Exception as e:
                            logger.warning(f"Error in progress callback: {e}")
                    
                    # Check if file matches patterns
                    if not self._matches_patterns(filename, include_patterns, exclude_patterns):
                        continue
                    
                    try:
                        # Get file info
                        file_info = self._create_file_info(file_path, validate_files)
                        files_found.append(file_info)
                        
                    except Exception as e:
                        error_msg = f"Error processing {file_path}: {e}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
        
        except Exception as e:
            error_msg = f"Error scanning directory {directory}: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
        
        # Calculate scan duration
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Scan completed: {len(files_found)} STL files found in {duration:.1f}s")
        
        return ScanResult(
            files_found=files_found,
            directories_scanned=directories_scanned,
            total_files_checked=total_files_checked,
            scan_duration=duration,
            errors=errors
        )
    
    def scan_multiple_paths(
        self,
        paths: List[Path],
        recursive: bool = True,
        validate_files: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> ScanResult:
        """
        Scan multiple files and directories.
        
        Args:
            paths: List of files and directories to scan
            recursive: Whether to scan directories recursively
            validate_files: Whether to validate STL files
            progress_callback: Optional progress callback
            
        Returns:
            ScanResult: Combined results from all paths
        """
        start_time = datetime.now()
        self._cancel_requested = False
        
        all_files: List[FileInfo] = []
        total_directories = 0
        total_files_checked = 0
        all_errors: List[str] = []
        
        for path in paths:
            if self._cancel_requested:
                break
            
            try:
                if path.is_file():
                    # Handle individual file
                    if path.suffix.lower() == '.stl':
                        total_files_checked += 1
                        if progress_callback:
                            progress_callback(len(all_files), total_files_checked, str(path))
                        
                        file_info = self._create_file_info(path, validate_files)
                        all_files.append(file_info)
                    
                elif path.is_dir():
                    # Handle directory
                    result = self.scan_directory(
                        path, recursive, validate_files, 
                        progress_callback=progress_callback
                    )
                    all_files.extend(result.files_found)
                    total_directories += result.directories_scanned
                    total_files_checked += result.total_files_checked
                    all_errors.extend(result.errors)
                    
                else:
                    error_msg = f"Path does not exist: {path}"
                    all_errors.append(error_msg)
                    logger.warning(error_msg)
                    
            except Exception as e:
                error_msg = f"Error processing path {path}: {e}"
                all_errors.append(error_msg)
                logger.error(error_msg)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return ScanResult(
            files_found=all_files,
            directories_scanned=total_directories,
            total_files_checked=total_files_checked,
            scan_duration=duration,
            errors=all_errors
        )
    
    def validate_stl_file(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Validate an STL file for basic readability.
        
        Args:
            file_path: Path to STL file to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check file size (empty files are invalid)
            if file_path.stat().st_size == 0:
                return False, "File is empty"
            
            # Try to read the first few bytes to check format
            with open(file_path, 'rb') as f:
                header = f.read(80)
                if len(header) < 80:
                    return False, "File too short to be valid STL"
                
                # Check if it's ASCII STL
                try:
                    header_str = header.decode('utf-8', errors='ignore').strip().lower()
                    if header_str.startswith('solid'):
                        # ASCII STL - check for 'endsolid'
                        f.seek(0)
                        content = f.read(1024).decode('utf-8', errors='ignore').lower()
                        if 'facet' not in content and 'vertex' not in content:
                            return False, "Invalid ASCII STL format"
                        return True, None
                except:
                    pass
                
                # Check if it's binary STL
                f.seek(80)
                triangle_count_bytes = f.read(4)
                if len(triangle_count_bytes) < 4:
                    return False, "Invalid binary STL header"
                
                # Basic sanity check on triangle count
                triangle_count = int.from_bytes(triangle_count_bytes, byteorder='little')
                expected_size = 80 + 4 + (triangle_count * 50)  # Header + count + triangles
                actual_size = file_path.stat().st_size
                
                if abs(actual_size - expected_size) > 100:  # Allow some tolerance
                    return False, f"File size mismatch (expected ~{expected_size}, got {actual_size})"
                
                return True, None
                
        except PermissionError:
            return False, "Permission denied accessing file"
        except Exception as e:
            return False, f"Error validating file: {e}"
    
    def calculate_file_checksum(self, file_path: Path, algorithm: str = 'md5') -> Optional[str]:
        """
        Calculate checksum for file.
        
        Args:
            file_path: Path to file
            algorithm: Hash algorithm ('md5', 'sha1', 'sha256')
            
        Returns:
            Hex string of checksum or None if error
        """
        try:
            hash_obj = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            logger.warning(f"Error calculating checksum for {file_path}: {e}")
            return None
    
    def cancel_scan(self):
        """Cancel ongoing scan operation."""
        with self._lock:
            self._cancel_requested = True
            logger.info("Scan cancellation requested")
    
    def is_cancelled(self) -> bool:
        """Check if scan has been cancelled."""
        with self._lock:
            return self._cancel_requested
    
    def _create_file_info(self, file_path: Path, validate: bool) -> FileInfo:
        """Create FileInfo object for a file."""
        try:
            stat = file_path.stat()
            file_info = FileInfo(
                path=file_path,
                size=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime)
            )
            
            if validate:
                is_valid, error = self.validate_stl_file(file_path)
                file_info.is_valid = is_valid
                file_info.validation_error = error
            
            return file_info
            
        except Exception as e:
            logger.error(f"Error creating file info for {file_path}: {e}")
            raise
    
    def _matches_patterns(self, filename: str, include_patterns: List[str], exclude_patterns: List[str]) -> bool:
        """Check if filename matches include/exclude patterns."""
        import fnmatch
        
        # Check exclude patterns first
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return False
        
        # Check include patterns
        if not include_patterns:
            return True  # No include patterns means include all
        
        for pattern in include_patterns:
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return True
        
        return False


def scan_for_stl_files(
    paths: List[Path],
    recursive: bool = True,
    validate_files: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> ScanResult:
    """
    Convenience function to scan for STL files.
    
    Args:
        paths: List of files/directories to scan
        recursive: Whether to scan directories recursively
        validate_files: Whether to validate STL files
        progress_callback: Optional progress callback
        
    Returns:
        ScanResult: Scan results
    """
    scanner = FileScanner()
    return scanner.scan_multiple_paths(paths, recursive, validate_files, progress_callback)


def find_duplicate_files(file_infos: List[FileInfo]) -> Dict[str, List[FileInfo]]:
    """
    Find duplicate files based on size and checksum.
    
    Args:
        file_infos: List of file information objects
        
    Returns:
        Dictionary mapping checksum to list of duplicate files
    """
    # Group by size first (quick check)
    size_groups: Dict[int, List[FileInfo]] = {}
    for file_info in file_infos:
        if file_info.size not in size_groups:
            size_groups[file_info.size] = []
        size_groups[file_info.size].append(file_info)
    
    # Check checksums for files with same size
    duplicates: Dict[str, List[FileInfo]] = {}
    
    for files_with_same_size in size_groups.values():
        if len(files_with_same_size) < 2:
            continue  # No duplicates possible
        
        # Calculate checksums for files with same size
        checksum_groups: Dict[str, List[FileInfo]] = {}
        
        for file_info in files_with_same_size:
            if not file_info.checksum:
                scanner = FileScanner()
                file_info.checksum = scanner.calculate_file_checksum(file_info.path)
            
            if file_info.checksum:
                if file_info.checksum not in checksum_groups:
                    checksum_groups[file_info.checksum] = []
                checksum_groups[file_info.checksum].append(file_info)
        
        # Add groups with multiple files to duplicates
        for checksum, files in checksum_groups.items():
            if len(files) > 1:
                duplicates[checksum] = files
    
    return duplicates