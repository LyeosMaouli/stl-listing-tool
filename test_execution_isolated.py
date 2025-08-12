"""
Isolated test runner to avoid queue module naming conflicts.
"""

import sys
import tempfile
import time
import traceback
from pathlib import Path

# Add src to path but avoid naming conflicts
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import execution classes directly to avoid module name conflicts
from batch_queue.job_types_v2 import Job, JobStatus, JobResult, JobError
from batch_queue.enhanced_job_manager import EnhancedJobManager


class MockJobExecutor:
    """Mock job executor for testing."""
    
    def __init__(self, execution_time=0.01, should_fail=False, error_message="Mock error"):
        self.execution_time = execution_time
        self.should_fail = should_fail
        self.error_message = error_message
        self.executions = []
    
    def can_handle(self, job: Job) -> bool:
        return job.job_type == "mock"
    
    def execute(self, job: Job, progress_callback=None) -> JobResult:
        self.executions.append(job.id)
        
        if progress_callback:
            progress_callback(0.0, "Starting mock job")
            time.sleep(self.execution_time / 2)
            progress_callback(0.5, "Halfway done")
            time.sleep(self.execution_time / 2)
            progress_callback(1.0, "Mock job complete")
        else:
            time.sleep(self.execution_time)
        
        if self.should_fail:
            return JobResult(
                job_id=job.id,
                success=False,
                error=JobError(
                    code="MOCK_ERROR",
                    message=self.error_message,
                    details={"mock": True}
                )
            )
        
        return JobResult(
            job_id=job.id,
            success=True,
            data={"mock_execution": True, "execution_time": self.execution_time}
        )
    
    def cleanup(self):
        pass


def test_enhanced_job_manager():
    """Test enhanced job manager with mock executor."""
    print("Testing enhanced job manager...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            manager = EnhancedJobManager(
                max_workers=1,
                state_dir=Path(temp_dir),
                auto_save=False,
                enable_recovery=False
            )
            
            # Register mock executor directly
            mock_executor = MockJobExecutor(execution_time=0.01)
            manager.execution_engine.register_executor("mock", mock_executor)
            
            # Add job
            job = Job(job_type="mock", input_file="test.stl")
            success = manager.add_job(job)
            assert success, "Adding job should succeed"
            
            # Check initial state
            summary = manager.get_queue_summary()
            assert summary["total_jobs"] == 1, "Should have 1 total job"
            assert summary["pending_jobs"] == 1, "Should have 1 pending job"
            
            # Start processing
            success = manager.start_processing()
            assert success, "Starting processing should succeed"
            
            # Wait for completion
            max_wait = 2.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                summary = manager.get_queue_summary()
                if summary["completed_jobs"] == 1:
                    break
                time.sleep(0.01)
            
            # Check final state
            summary = manager.get_queue_summary()
            assert summary["completed_jobs"] == 1, f"Should have 1 completed job, got: {summary}"
            assert job.status == JobStatus.COMPLETED, f"Job status should be completed, got: {job.status}"
            
            print("✓ Enhanced job manager test passed")
            return True
            
        except Exception as e:
            print(f"✗ Enhanced job manager test failed: {e}")
            print(f"  Traceback: {traceback.format_exc()}")
            return False
        
        finally:
            try:
                manager.shutdown()
            except:
                pass


def run_tests():
    """Run all tests."""
    print("Running isolated job execution tests...\n")
    
    success = test_enhanced_job_manager()
    
    if success:
        print("\n🎉 Isolated test passed!")
        return True
    else:
        print("\n❌ Isolated test failed")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)