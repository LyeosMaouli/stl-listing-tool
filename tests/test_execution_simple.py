"""
Simple test runner for job execution system without pytest dependency.
"""

import sys
import tempfile
import time
import traceback
from pathlib import Path

# Add src to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "src"))

from queue.job_types_v2 import Job, JobStatus, JobResult, JobError
from queue.job_executor import JobExecutor, JobExecutionEngine
from queue.enhanced_job_manager import EnhancedJobManager


class MockJobExecutor(JobExecutor):
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


def test_basic_job_execution():
    """Test basic job execution."""
    print("Testing basic job execution...")
    
    executor = MockJobExecutor(execution_time=0.01)
    job = Job(job_type="mock", input_file="test.stl")
    
    result = executor.execute(job)
    
    assert result.success, "Job should succeed"
    assert result.job_id == job.id, "Job ID should match"
    assert job.id in executor.executions, "Job should be recorded as executed"
    
    print("✓ Basic job execution test passed")


def test_job_failure():
    """Test job failure handling."""
    print("Testing job failure...")
    
    executor = MockJobExecutor(should_fail=True, error_message="Test error")
    job = Job(job_type="mock", input_file="test.stl")
    
    result = executor.execute(job)
    
    assert not result.success, "Job should fail"
    assert result.error.code == "MOCK_ERROR", "Error code should match"
    assert result.error.message == "Test error", "Error message should match"
    
    print("✓ Job failure test passed")


def test_execution_engine():
    """Test job execution engine."""
    print("Testing execution engine...")
    
    engine = JobExecutionEngine(max_workers=1)
    executor = MockJobExecutor(execution_time=0.01)
    engine.register_executor("mock", executor)
    
    try:
        job = Job(job_type="mock", input_file="test.stl")
        future = engine.submit_job(job)
        
        result = future.result(timeout=1.0)
        
        assert result.success, "Job should succeed"
        assert job.status == JobStatus.COMPLETED, "Job status should be completed"
        assert job.id in executor.executions, "Job should be executed"
        
        print("✓ Execution engine test passed")
    
    finally:
        engine.shutdown()


def test_enhanced_job_manager():
    """Test enhanced job manager."""
    print("Testing enhanced job manager...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = EnhancedJobManager(
            max_workers=1,
            state_dir=Path(temp_dir),
            auto_save=False,
            enable_recovery=False
        )
        
        # Register mock executor
        mock_executor = MockJobExecutor(execution_time=0.01)
        manager.execution_engine.register_executor("mock", mock_executor)
        
        try:
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
        
        finally:
            manager.shutdown()


def test_multiple_jobs():
    """Test processing multiple jobs."""
    print("Testing multiple jobs...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = EnhancedJobManager(
            max_workers=2,
            state_dir=Path(temp_dir),
            auto_save=False,
            enable_recovery=False
        )
        
        mock_executor = MockJobExecutor(execution_time=0.01)
        manager.execution_engine.register_executor("mock", mock_executor)
        
        try:
            # Add multiple jobs
            jobs = []
            for i in range(5):
                job = Job(job_type="mock", input_file=f"test{i}.stl")
                jobs.append(job)
                manager.add_job(job)
            
            # Start processing
            manager.start_processing()
            
            # Wait for all jobs to complete
            max_wait = 5.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                summary = manager.get_queue_summary()
                if summary["completed_jobs"] == 5:
                    break
                time.sleep(0.01)
            
            # Check results
            summary = manager.get_queue_summary()
            assert summary["completed_jobs"] == 5, f"Should have 5 completed jobs, got: {summary}"
            assert len(mock_executor.executions) == 5, f"Should have executed 5 jobs, got: {len(mock_executor.executions)}"
            
            for job in jobs:
                assert job.status == JobStatus.COMPLETED, f"Job {job.id} should be completed, got: {job.status}"
                assert job.id in mock_executor.executions, f"Job {job.id} should be in executions"
            
            print("✓ Multiple jobs test passed")
        
        finally:
            manager.shutdown()


def run_all_tests():
    """Run all tests."""
    tests = [
        test_basic_job_execution,
        test_job_failure,
        test_execution_engine,
        test_enhanced_job_manager,
        test_multiple_jobs
    ]
    
    passed = 0
    failed = 0
    
    print("Running job execution tests...\n")
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            print(f"  Traceback: {traceback.format_exc()}")
            failed += 1
    
    print(f"\nTest Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)