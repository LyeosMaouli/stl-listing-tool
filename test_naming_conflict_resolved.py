"""
Test to verify the queue module naming conflict is resolved.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import our batch_queue module
from batch_queue.job_types_v2 import Job, JobStatus, JobResult, JobError
from batch_queue.enhanced_job_manager import EnhancedJobManager

# Test that Python's built-in queue module still works
import queue as python_queue
from concurrent.futures import ThreadPoolExecutor

def test_python_queue_module():
    """Test that Python's built-in queue module works."""
    print("Testing Python's built-in queue module...")
    
    # Test SimpleQueue
    q = python_queue.SimpleQueue()
    q.put("test")
    item = q.get()
    assert item == "test", "SimpleQueue should work"
    
    # Test ThreadPoolExecutor (which uses queue.SimpleQueue internally)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: "test_result")
        result = future.result()
        assert result == "test_result", "ThreadPoolExecutor should work"
    
    print("✓ Python's built-in queue module works correctly")


def test_batch_queue_module():
    """Test that our batch_queue module works."""
    print("Testing our batch_queue module...")
    
    # Test basic job creation
    job = Job(job_type="test", input_file="test.stl")
    assert job.status == JobStatus.PENDING, "Job should start as pending"
    
    # Test enhanced job manager can be created
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = EnhancedJobManager(
            max_workers=1,
            state_dir=Path(temp_dir),
            auto_save=False,
            enable_recovery=False
        )
        
        # Test that ThreadPoolExecutor can be created inside our module
        manager.execution_engine.start()
        assert manager.execution_engine.executor_pool is not None, "ThreadPoolExecutor should be created"
        
        manager.shutdown()
    
    print("✓ Our batch_queue module works correctly")


def test_no_naming_conflict():
    """Test that there's no naming conflict between modules."""
    print("Testing no naming conflict...")
    
    # Both should be importable without issues
    import queue as builtin_queue
    import batch_queue
    
    # They should be different modules
    assert builtin_queue != batch_queue, "Should be different modules"
    
    # Built-in queue should have SimpleQueue
    assert hasattr(builtin_queue, 'SimpleQueue'), "Built-in queue should have SimpleQueue"
    
    # Our batch_queue should have our classes
    assert hasattr(batch_queue, 'EnhancedJobManager'), "batch_queue should have EnhancedJobManager"
    
    print("✓ No naming conflict detected")


def main():
    """Run all tests."""
    print("🧪 Testing queue module naming conflict resolution...\n")
    
    try:
        test_python_queue_module()
        test_batch_queue_module()
        test_no_naming_conflict()
        
        print("\n🎉 All tests passed! Queue module naming conflict is resolved!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)