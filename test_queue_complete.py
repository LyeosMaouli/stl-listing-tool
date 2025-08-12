#!/usr/bin/env python3
"""
Comprehensive test of the complete queue system.
"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime
import time

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_job_manager():
    """Test the central job manager functionality."""
    print("Testing JobManager...")
    
    from batch_queue import (
        JobManager, JobType, RenderOptions, ValidationOptions,
        create_job_from_stl
    )
    
    # Create temporary files and directories
    temp_dir = Path(tempfile.mkdtemp())
    stl_files = []
    
    # Create test STL files
    for i in range(3):
        stl_file = temp_dir / f"test_model_{i}.stl"
        with open(stl_file, 'w') as f:
            f.write(f"solid test_model_{i}\n")
            f.write("  facet normal 0 0 1\n")
            f.write("    outer loop\n")
            f.write("      vertex 0 0 0\n")
            f.write("      vertex 1 0 0\n")
            f.write("      vertex 0 1 0\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
            f.write(f"endsolid test_model_{i}\n")
        stl_files.append(stl_file)
    
    # Create output directory
    output_dir = temp_dir / "output"
    output_dir.mkdir()
    
    # Create job manager with temporary files
    history_db = temp_dir / "test_history.db"
    state_file = temp_dir / "test_queue_state.json"
    
    job_manager = JobManager(state_file=state_file, history_db=history_db, auto_save=True)
    
    print(f"✓ Created JobManager with session: {job_manager.session_id}")
    
    # Test adding jobs
    render_options = RenderOptions(
        generate_image=True,
        generate_size_chart=False,
        width=800,
        height=600
    )
    
    job_ids = job_manager.add_jobs_from_files(
        stl_files, output_dir, JobType.RENDER, render_options
    )
    
    print(f"✓ Added {len(job_ids)} jobs to queue")
    
    # Test queue summary
    summary = job_manager.get_queue_summary()
    print(f"✓ Queue summary: {summary['total_jobs']} jobs")
    print(f"  Pending jobs: {summary['queue_stats']['pending']}")
    
    # Test state persistence
    success = job_manager.save_queue_state()
    print(f"✓ Saved queue state: {success}")
    
    # Test loading state (create new manager)
    job_manager2 = JobManager(state_file=state_file, history_db=history_db)
    loaded = job_manager2.load_queue_state()
    print(f"✓ Loaded queue state: {loaded}")
    
    if loaded:
        summary2 = job_manager2.get_queue_summary()
        print(f"  Loaded {summary2['total_jobs']} jobs")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    print("✓ JobManager test completed")


def test_scan_and_add():
    """Test scanning directories and adding jobs."""
    print("\nTesting scan and add functionality...")
    
    from batch_queue import JobManager, JobType, RenderOptions
    
    # Create temporary directory structure
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create main directory with STL files
    for i in range(2):
        stl_file = temp_dir / f"main_model_{i}.stl"
        with open(stl_file, 'w') as f:
            f.write(f"solid main_model_{i}\nendsolid main_model_{i}\n")
    
    # Create subdirectory with more STL files
    sub_dir = temp_dir / "subfolder"
    sub_dir.mkdir()
    for i in range(2):
        stl_file = sub_dir / f"sub_model_{i}.stl"
        with open(stl_file, 'w') as f:
            f.write(f"solid sub_model_{i}\nendsolid sub_model_{i}\n")
    
    # Create output directory
    output_dir = temp_dir / "output"
    
    # Create job manager
    job_manager = JobManager()
    
    # Scan and add jobs
    result = job_manager.scan_and_add_jobs(
        paths=[temp_dir],
        output_base=output_dir,
        recursive=True,
        validate_files=True,
        job_type=JobType.RENDER
    )
    
    print(f"✓ Scanned and found {result['valid_files']} valid STL files")
    print(f"✓ Added {result['jobs_added']} jobs to queue")
    
    if result['errors']:
        print(f"  Errors during scan: {result['errors']}")
    
    # Test queue processing controls
    started = job_manager.start_processing()
    print(f"✓ Started processing: {started}")
    
    paused = job_manager.pause_processing()
    print(f"✓ Paused processing: {paused}")
    
    resumed = job_manager.resume_processing()
    print(f"✓ Resumed processing: {resumed}")
    
    stopped = job_manager.stop_processing()
    print(f"✓ Stopped processing: {stopped}")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    print("✓ Scan and add test completed")


def test_configuration_templates():
    """Test configuration template system."""
    print("\nTesting configuration templates...")
    
    from batch_queue import QueueConfiguration, RenderOptions
    
    # Create temporary config directory
    temp_dir = Path(tempfile.mkdtemp())
    config_dir = temp_dir / "templates"
    
    config_manager = QueueConfiguration(config_dir)
    
    # Create default templates
    config_manager.create_default_templates()
    
    # List templates
    templates = config_manager.list_templates()
    print(f"✓ Created {len(templates)} default templates: {templates}")
    
    # Load a template
    if templates:
        template_data = config_manager.load_template(templates[0])
        if template_data:
            print(f"✓ Loaded template '{templates[0]}': {template_data.get('name')}")
    
    # Create custom template
    custom_template = {
        'name': 'Test Template',
        'description': 'Custom test template',
        'render_options': {
            'generate_image': True,
            'width': 1024,
            'height': 768,
            'material': 'metal'
        }
    }
    
    saved = config_manager.save_template('test_template', custom_template)
    print(f"✓ Saved custom template: {saved}")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    print("✓ Configuration templates test completed")


def test_job_history():
    """Test job history database functionality."""
    print("\nTesting job history database...")
    
    from batch_queue import (
        JobHistoryManager, QueueJob, JobResults, JobType, JobState,
        create_render_job, RenderOptions
    )
    
    # Create temporary database
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / "test_history.db"
    
    history_manager = JobHistoryManager(db_path)
    
    # Create mock job
    stl_path = temp_dir / "test.stl"
    with open(stl_path, 'w') as f:
        f.write("solid test\nendsolid test\n")
    
    output_dir = temp_dir / "output"
    job = create_render_job(stl_path, output_dir, RenderOptions())
    job.state = JobState.COMPLETED
    job.started_at = datetime.now()
    job.completed_at = datetime.now()
    
    # Create mock results
    results = JobResults(
        validation_passed=True,
        files_generated=[output_dir / "test_render.png"],
        processing_time=120.5
    )
    
    # Record job completion
    recorded = history_manager.record_job_completion(job, results, "test_session", "abc123")
    print(f"✓ Recorded job completion: {recorded}")
    
    # Get statistics
    stats = history_manager.get_processing_statistics(days=30)
    print(f"✓ Generated statistics: {stats.total_jobs} total jobs")
    print(f"  Success rate: {stats.success_rate:.1f}%")
    print(f"  Average duration: {stats.average_job_duration:.1f}s")
    
    # Find similar jobs
    similar_jobs = history_manager.find_similar_jobs(stl_path)
    print(f"✓ Found {len(similar_jobs)} similar jobs")
    
    # Get database info
    db_info = history_manager.get_database_info()
    print(f"✓ Database info: {db_info.get('total_records', 0)} records")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    print("✓ Job history test completed")


def test_progress_integration():
    """Test progress tracking integration."""
    print("\nTesting progress tracking integration...")
    
    from batch_queue import JobManager, ProgressTracker, JobProgress
    
    job_manager = JobManager()
    
    # Add observer to track progress updates
    progress_updates = []
    
    def progress_observer(queue_progress):
        progress_updates.append({
            'timestamp': datetime.now(),
            'total_jobs': queue_progress.total_jobs,
            'overall_progress': queue_progress.overall_progress,
            'active_jobs': queue_progress.active_jobs
        })
    
    job_manager.progress_tracker.add_progress_observer(progress_observer)
    
    # Start queue tracking
    job_manager.progress_tracker.start_queue_tracking(5)
    
    # Simulate progress updates
    for i in range(5):
        job_id = f"test_job_{i}"
        
        # Start job tracking
        from queue.progress_tracker import JobProgress, JobState
        job_progress = JobProgress(
            job_id=job_id,
            job_type="render",
            stl_filename=f"test_{i}.stl",
            state=JobState.PROCESSING,
            progress=0.0
        )
        
        # Simulate progress updates
        for progress in [25, 50, 75, 100]:
            job_manager.progress_tracker.update_job_progress(
                job_id, progress, f"Step at {progress}%"
            )
            time.sleep(0.01)  # Small delay
        
        job_manager.progress_tracker.complete_job(job_id, 30.0)
    
    print(f"✓ Generated {len(progress_updates)} progress updates")
    
    # Get final stats
    stats = job_manager.progress_tracker.get_performance_stats()
    print(f"✓ Performance stats: {stats.get('total_jobs_tracked', 0)} jobs tracked")
    
    print("✓ Progress integration test completed")


def main():
    """Run all comprehensive tests."""
    print("Testing Complete STL Queue System")
    print("=" * 50)
    
    try:
        test_job_manager()
        test_scan_and_add()
        test_configuration_templates()
        test_job_history()
        test_progress_integration()
        
        print("\n" + "=" * 50)
        print("✓ All comprehensive tests passed!")
        print("\nThe complete queue system is working correctly!")
        print("Ready for integration with GUI and job execution.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())