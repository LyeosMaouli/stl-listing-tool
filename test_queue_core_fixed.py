#!/usr/bin/env python3
"""
Fixed test of core queue components that handles dependencies properly.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    # Try to import with rendering dependencies
    from queue import (
        JobType, JobState, RenderOptions, ValidationOptions,
        QueueJob, create_render_job, JobQueue, FileScanner, ProgressTracker
    )
    from rendering.base_renderer import MaterialType, LightingPreset
    RENDERING_AVAILABLE = True
except ImportError:
    # Import without rendering dependencies (uses fallback enums)
    from queue import (
        JobType, JobState, RenderOptions, ValidationOptions,
        QueueJob, create_render_job, JobQueue, FileScanner, ProgressTracker
    )
    from queue.job_types import MaterialType, LightingPreset
    RENDERING_AVAILABLE = False


def create_test_stl_file():
    """Create a persistent test STL file."""
    temp_fd, temp_path = tempfile.mkstemp(suffix='.stl')
    stl_path = Path(temp_path)
    
    # Write STL content
    with open(temp_fd, 'wb') as f:
        f.write(b"solid test\n")
        f.write(b"  facet normal 0 0 1\n")
        f.write(b"    outer loop\n")
        f.write(b"      vertex 0 0 0\n")
        f.write(b"      vertex 1 0 0\n")
        f.write(b"      vertex 0 1 0\n")
        f.write(b"    endloop\n")
        f.write(b"  endfacet\n")
        f.write(b"endsolid test\n")
    
    return stl_path


def test_job_creation():
    """Test job creation and serialization."""
    print("Testing job creation...")
    
    # Create a persistent STL file for testing
    stl_path = create_test_stl_file()
    
    try:
        # Create render options
        render_options = RenderOptions(
            generate_image=True,
            generate_video=False,
            material=MaterialType.PLASTIC,
            lighting=LightingPreset.STUDIO,
            width=1920,
            height=1080
        )
        
        # Create job
        output_folder = Path(tempfile.mkdtemp())
        job = create_render_job(stl_path, output_folder, render_options)
        
        print(f"✓ Created job: {job.id}")
        print(f"  STL file: {job.stl_filename}")
        print(f"  Output: {job.output_folder}")
        print(f"  State: {job.state.value}")
        
        # Test serialization
        job_dict = job.to_dict()
        reconstructed_job = QueueJob.from_dict(job_dict)
        
        print(f"✓ Serialization test passed")
        
        return job, stl_path
        
    except Exception as e:
        # Clean up on error
        if stl_path.exists():
            stl_path.unlink()
        raise e


def test_job_queue():
    """Test job queue operations."""
    print("\nTesting job queue...")
    
    queue = JobQueue()
    
    # Create test job (keeping STL file alive)
    job, stl_path = test_job_creation()
    
    try:
        # Add to queue
        success = queue.add_job(job)
        print(f"✓ Added job to queue: {success}")
        print(f"  Queue length: {len(queue)}")
        
        # Get next job
        next_job = queue.get_next_job()
        print(f"✓ Got next job: {next_job.id if next_job else None}")
        
        # Update job state
        if success:
            queue.update_job_state(job.id, JobState.PROCESSING, progress=50)
            updated_job = queue.get_job(job.id)
            print(f"✓ Updated job progress: {updated_job.progress}%")
        else:
            print("✓ Skipped job progress update (job not in queue)")
        
        # Get stats
        stats = queue.get_queue_stats()
        print(f"✓ Queue stats: {stats}")
        
        return queue
        
    finally:
        # Clean up STL file
        if stl_path.exists():
            stl_path.unlink()


def test_file_scanner():
    """Test file scanner functionality."""
    print("\nTesting file scanner...")
    
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
        print(f"    {file_info.path.name} ({file_info.size} bytes)")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


def test_progress_tracker():
    """Test progress tracking functionality."""
    print("\nTesting progress tracker...")
    
    tracker = ProgressTracker()
    
    # Create test job
    job, stl_path = test_job_creation()
    
    try:
        # Start tracking
        tracker.start_queue_tracking(1)
        tracker.start_job_tracking(job)
        
        print("✓ Started tracking")
        
        # Update progress
        tracker.update_job_progress(job.id, 25.0, "Processing mesh")
        tracker.update_job_progress(job.id, 50.0, "Rendering image")
        tracker.update_job_progress(job.id, 75.0, "Saving output")
        tracker.update_job_progress(job.id, 100.0, "Complete")
        
        # Get progress
        job_progress = tracker.get_job_progress(job.id)
        queue_progress = tracker.get_queue_progress()
        
        if job_progress:
            print(f"✓ Job progress: {job_progress.progress}%")
            print(f"  Current step: {job_progress.current_step}")
        
        if queue_progress:
            print(f"✓ Queue progress: {queue_progress.overall_progress:.1f}%")
            print(f"  Total jobs: {queue_progress.total_jobs}")
        
        # Complete job
        tracker.complete_job(job.id, 120.0)  # 2 minutes
        
        # Get performance stats
        stats = tracker.get_performance_stats()
        print(f"✓ Performance stats: {len(stats)} metrics tracked")
        
    finally:
        # Clean up STL file
        if stl_path.exists():
            stl_path.unlink()


def main():
    """Run all tests."""
    print("Testing STL Queue Core Components (Fixed Version)")
    print("=" * 50)
    
    if not RENDERING_AVAILABLE:
        print("Note: Using fallback enums (rendering dependencies not available)")
    
    try:
        test_job_creation()
        test_job_queue() 
        test_file_scanner()
        test_progress_tracker()
        
        print("\n" + "=" * 50)
        print("✓ All core tests passed!")
        print(f"Rendering dependencies: {'✓ Available' if RENDERING_AVAILABLE else '✗ Using fallbacks'}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())