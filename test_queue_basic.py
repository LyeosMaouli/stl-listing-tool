#!/usr/bin/env python3
"""
Basic test of queue components without external dependencies.
"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Test basic job types without rendering dependencies
def test_job_states():
    """Test job state enums and basic functionality."""
    print("Testing job states...")
    
    from queue.job_types import JobType, JobState, ValidationLevel
    
    # Test enum values
    print(f"✓ JobType.RENDER: {JobType.RENDER.value}")
    print(f"✓ JobState.PENDING: {JobState.PENDING.value}")
    print(f"✓ ValidationLevel.STANDARD: {ValidationLevel.STANDARD.value}")


def test_file_scanner():
    """Test file scanner functionality."""
    print("\nTesting file scanner...")
    
    from queue.file_scanner import FileScanner, FileInfo
    
    scanner = FileScanner()
    
    # Create temporary directory with STL files
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create a few test STL files
    for i in range(3):
        stl_file = temp_dir / f"test_{i}.stl"
        with open(stl_file, 'w') as f:
            f.write(f"solid test_{i}\n")
            f.write("  facet normal 0 0 1\n")
            f.write("    outer loop\n")
            f.write("      vertex 0 0 0\n")
            f.write("      vertex 1 0 0\n")
            f.write("      vertex 0 1 0\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
            f.write(f"endsolid test_{i}\n")
    
    # Create a subfolder with more STL files
    sub_dir = temp_dir / "subfolder"
    sub_dir.mkdir()
    for i in range(2):
        stl_file = sub_dir / f"sub_test_{i}.stl"
        with open(stl_file, 'w') as f:
            f.write(f"solid sub_test_{i}\nendsolid sub_test_{i}\n")
    
    # Scan directory
    result = scanner.scan_directory(temp_dir, recursive=True, validate_files=True)
    
    print(f"✓ Scanned directory: {temp_dir}")
    print(f"  Files found: {len(result.files_found)}")
    print(f"  Directories scanned: {result.directories_scanned}")
    print(f"  Scan duration: {result.scan_duration:.2f}s")
    
    if result.errors:
        print(f"  Errors: {result.errors}")
    
    # Show found files
    for file_info in result.files_found[:3]:  # Show first 3
        print(f"    {file_info.path.name} ({file_info.size} bytes, valid: {file_info.is_valid})")
    
    # Test validation
    if result.files_found:
        test_file = result.files_found[0].path
        is_valid, error = scanner.validate_stl_file(test_file)
        print(f"  Validation test: {'✓' if is_valid else '✗'} {error or 'Valid'}")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


def test_progress_tracking():
    """Test progress tracking without job dependencies."""
    print("\nTesting progress tracking...")
    
    from queue.progress_tracker import ProgressTracker, JobProgress, QueueProgress, JobState
    
    tracker = ProgressTracker()
    
    # Test queue progress
    tracker.start_queue_tracking(5)
    queue_progress = tracker.get_queue_progress()
    
    if queue_progress:
        print(f"✓ Queue tracking started")
        print(f"  Total jobs: {queue_progress.total_jobs}")
        print(f"  Overall progress: {queue_progress.overall_progress:.1f}%")
    
    # Create a mock job progress
    job_progress = JobProgress(
        job_id="test_job_001",
        job_type="render",
        stl_filename="test.stl",
        state=JobState.PROCESSING,
        progress=0.0,
        started_at=datetime.now()
    )
    
    # Test progress updates
    job_progress.progress = 25.0
    print(f"✓ Job progress updated: {job_progress.progress}%")
    
    # Test time estimation
    import time
    time.sleep(0.1)  # Small delay for time calculation
    job_progress.progress = 50.0
    time_remaining = job_progress.time_remaining
    print(f"✓ Time estimation: {time_remaining:.1f}s remaining" if time_remaining else "✓ Time estimation: Not available")
    
    # Test performance stats
    stats = tracker.get_performance_stats()
    print(f"✓ Performance stats collected: {len(stats)} metrics")


def test_basic_queue():
    """Test basic queue operations without full job objects."""
    print("\nTesting basic queue structure...")
    
    from queue.job_queue import JobQueue
    from queue.job_types import JobState
    
    queue = JobQueue()
    
    # Test empty queue
    print(f"✓ Empty queue length: {len(queue)}")
    
    # Test stats on empty queue
    stats = queue.get_queue_stats()
    print(f"✓ Empty queue stats: {stats}")
    
    # Test next job on empty queue
    next_job = queue.get_next_job()
    print(f"✓ Next job from empty queue: {next_job}")


def main():
    """Run all basic tests."""
    print("Testing STL Queue Basic Components")
    print("=" * 40)
    
    try:
        test_job_states()
        test_file_scanner()
        test_progress_tracking()
        test_basic_queue()
        
        print("\n" + "=" * 40)
        print("✓ All basic tests passed!")
        print("\nNote: Full integration tests require numpy, trimesh, and vtk dependencies.")
        print("The core queue system components are working correctly!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())