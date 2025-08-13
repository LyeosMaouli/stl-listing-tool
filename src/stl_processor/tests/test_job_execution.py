"""
Comprehensive tests for the job execution system.
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

from src.batch_queue.job_types import Job, JobStatus, JobResult, JobError
from src.batch_queue.job_executor import JobExecutor, JobExecutionEngine
from src.batch_queue.error_handler import ErrorHandler
from src.batch_queue.enhanced_job_manager import EnhancedJobManager


# Mock job executor for testing
class MockJobExecutor(JobExecutor):
    """Mock job executor for testing."""
    
    def __init__(self, execution_time=0.1, should_fail=False, error_message="Mock error"):
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


class TestJobExecutor:
    """Test job executor base functionality."""
    
    def test_mock_executor_can_handle(self):
        executor = MockJobExecutor()
        
        job = Job(job_type="mock", input_file="test.stl")
        assert executor.can_handle(job)
        
        job = Job(job_type="render", input_file="test.stl")
        assert not executor.can_handle(job)
    
    def test_mock_executor_success(self):
        executor = MockJobExecutor(execution_time=0.01)
        job = Job(job_type="mock", input_file="test.stl")
        
        result = executor.execute(job)
        
        assert result.success
        assert result.job_id == job.id
        assert result.data["mock_execution"] is True
        assert job.id in executor.executions
    
    def test_mock_executor_failure(self):
        executor = MockJobExecutor(should_fail=True, error_message="Test error")
        job = Job(job_type="mock", input_file="test.stl")
        
        result = executor.execute(job)
        
        assert not result.success
        assert result.error.code == "MOCK_ERROR"
        assert result.error.message == "Test error"
    
    def test_mock_executor_progress_callback(self):
        executor = MockJobExecutor(execution_time=0.01)
        job = Job(job_type="mock", input_file="test.stl")
        
        progress_calls = []
        def progress_callback(progress, message):
            progress_calls.append((progress, message))
        
        result = executor.execute(job, progress_callback)
        
        assert result.success
        assert len(progress_calls) == 3
        assert progress_calls[0] == (0.0, "Starting mock job")
        assert progress_calls[1] == (0.5, "Halfway done")
        assert progress_calls[2] == (1.0, "Mock job complete")


class TestJobExecutionEngine:
    """Test job execution engine."""
    
    def test_engine_initialization(self):
        engine = JobExecutionEngine(max_workers=2)
        
        assert engine.max_workers == 2
        assert engine.executor_pool is None
        assert len(engine.executors) == 0
        assert not engine.is_paused()
    
    def test_register_executor(self):
        engine = JobExecutionEngine()
        executor = MockJobExecutor()
        
        engine.register_executor("mock", executor)
        
        assert "mock" in engine.executors
        assert engine.executors["mock"] is executor
    
    def test_unregister_executor(self):
        engine = JobExecutionEngine()
        executor = MockJobExecutor()
        
        engine.register_executor("mock", executor)
        engine.unregister_executor("mock")
        
        assert "mock" not in engine.executors
    
    def test_start_and_shutdown(self):
        engine = JobExecutionEngine(max_workers=1)
        
        # Start engine
        engine.start()
        assert engine.executor_pool is not None
        
        # Shutdown engine
        engine.shutdown()
        assert engine.executor_pool is None
    
    def test_pause_and_resume(self):
        engine = JobExecutionEngine()
        
        # Initially not paused
        assert not engine.is_paused()
        
        # Pause
        engine.pause()
        assert engine.is_paused()
        
        # Resume
        engine.resume()
        assert not engine.is_paused()
    
    def test_submit_job_success(self):
        engine = JobExecutionEngine(max_workers=1)
        executor = MockJobExecutor(execution_time=0.01)
        engine.register_executor("mock", executor)
        
        job = Job(job_type="mock", input_file="test.stl")
        future = engine.submit_job(job)
        
        # Wait for completion
        result = future.result(timeout=1.0)
        
        assert result.success
        assert job.status == JobStatus.COMPLETED
        assert job.id in executor.executions
        
        engine.shutdown()
    
    def test_submit_job_failure(self):
        engine = JobExecutionEngine(max_workers=1)
        executor = MockJobExecutor(should_fail=True, error_message="Test failure")
        engine.register_executor("mock", executor)
        
        job = Job(job_type="mock", input_file="test.stl")
        future = engine.submit_job(job)
        
        # Wait for completion
        result = future.result(timeout=1.0)
        
        assert not result.success
        assert result.error.message == "Test failure"
        assert job.status == JobStatus.FAILED
        
        engine.shutdown()
    
    def test_submit_job_no_executor(self):
        engine = JobExecutionEngine(max_workers=1)
        
        job = Job(job_type="nonexistent", input_file="test.stl")
        future = engine.submit_job(job)
        
        # Should fail immediately
        with pytest.raises(RuntimeError, match="No executor found"):
            future.result(timeout=1.0)
        
        engine.shutdown()
    
    def test_cancel_job(self):
        engine = JobExecutionEngine(max_workers=1)
        executor = MockJobExecutor(execution_time=1.0)  # Long running job
        engine.register_executor("mock", executor)
        
        job = Job(job_type="mock", input_file="test.stl")
        future = engine.submit_job(job)
        
        # Cancel job quickly
        time.sleep(0.1)
        success = engine.cancel_job(job.id)
        
        assert success
        assert future.cancelled()
        
        engine.shutdown()
    
    def test_pause_during_execution(self):
        engine = JobExecutionEngine(max_workers=1)
        executor = MockJobExecutor(execution_time=0.5)
        engine.register_executor("mock", executor)
        
        job = Job(job_type="mock", input_file="test.stl")
        
        # Pause engine before submitting
        engine.pause()
        
        future = engine.submit_job(job)
        
        # Job should not start immediately
        time.sleep(0.1)
        assert job.status == JobStatus.PENDING
        
        # Resume and wait for completion
        engine.resume()
        result = future.result(timeout=1.0)
        
        assert result.success
        assert job.status == JobStatus.COMPLETED
        
        engine.shutdown()


class TestErrorHandler:
    """Test error handling system."""
    
    def test_error_classification(self):
        handler = ErrorHandler()
        
        # Test file error
        error = JobError(code="STL_LOAD_FAILED", message="Failed to load file")
        job = Job(job_type="mock", input_file="test.stl")
        
        result = handler.handle_error(job, error)
        
        assert result["action"] == "retry"
        assert "delay" in result
        assert result["retry_count"] > 0
    
    def test_retry_limit(self):
        handler = ErrorHandler()
        job = Job(job_type="mock", input_file="test.stl")
        error = JobError(code="PERMANENT_ERROR", message="Cannot be fixed")
        
        # Simulate multiple failures
        for i in range(5):  # Exceed retry limits
            result = handler.handle_error(job, error)
        
        # Should eventually fail permanently
        assert result["action"] == "fail"
        assert job.status == JobStatus.FAILED
    
    def test_error_statistics(self):
        handler = ErrorHandler()
        job = Job(job_type="mock", input_file="test.stl")
        
        # Generate some errors
        error1 = JobError(code="RENDER_FAILED", message="Render failed")
        error2 = JobError(code="STL_LOAD_FAILED", message="Load failed")
        
        handler.handle_error(job, error1)
        handler.handle_error(job, error2)
        
        stats = handler.get_error_statistics()
        
        assert stats["total_errors"] >= 2
        assert "errors_by_category" in stats
        assert "recoveries_by_strategy" in stats


class TestEnhancedJobManager:
    """Test enhanced job manager with execution."""
    
    def setup_method(self):
        """Setup for each test."""
        # Create temporary directory for state
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Create manager with minimal workers and no recovery for testing
        self.manager = EnhancedJobManager(
            max_workers=1,
            state_dir=self.temp_dir,
            auto_save=False,
            enable_recovery=False
        )
        
        # Register mock executor
        self.mock_executor = MockJobExecutor(execution_time=0.01)
        self.manager.execution_engine.register_executor("mock", self.mock_executor)
    
    def teardown_method(self):
        """Cleanup after each test."""
        if hasattr(self, 'manager'):
            self.manager.shutdown()
        
        # Cleanup temp directory
        import shutil
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_add_job(self):
        job = Job(job_type="mock", input_file="test.stl")
        
        success = self.manager.add_job(job)
        
        assert success
        assert job.id in self.manager._jobs
        assert job.id in self.manager._pending_jobs
        assert job.status == JobStatus.PENDING
    
    def test_start_processing(self):
        job = Job(job_type="mock", input_file="test.stl")
        self.manager.add_job(job)
        
        success = self.manager.start_processing()
        
        assert success
        assert self.manager.is_running
        
        # Wait for job completion
        time.sleep(0.2)
        
        summary = self.manager.get_queue_summary()
        assert summary["completed_jobs"] == 1
        assert job.status == JobStatus.COMPLETED
    
    def test_pause_resume_processing(self):
        job = Job(job_type="mock", input_file="test.stl")
        self.manager.add_job(job)
        
        # Start processing
        self.manager.start_processing()
        
        # Pause
        success = self.manager.pause_processing()
        assert success
        assert self.manager.is_paused
        
        # Resume
        success = self.manager.resume_processing()
        assert success
        assert not self.manager.is_paused
    
    def test_stop_processing(self):
        job = Job(job_type="mock", input_file="test.stl")
        self.manager.add_job(job)
        
        # Start processing
        self.manager.start_processing()
        
        # Stop
        success = self.manager.stop_processing()
        assert success
        assert not self.manager.is_running
        assert not self.manager.is_paused
    
    def test_job_failure_handling(self):
        # Use failing mock executor
        failing_executor = MockJobExecutor(should_fail=True, error_message="Test failure")
        self.manager.execution_engine.register_executor("failing", failing_executor)
        
        job = Job(job_type="failing", input_file="test.stl")
        self.manager.add_job(job)
        
        self.manager.start_processing()
        
        # Wait for processing
        time.sleep(0.2)
        
        # Check that error handling was applied
        summary = self.manager.get_queue_summary()
        assert summary["failed_jobs"] >= 1 or summary["pending_jobs"] >= 1  # Might be retried
    
    def test_remove_job(self):
        job = Job(job_type="mock", input_file="test.stl")
        self.manager.add_job(job)
        
        success = self.manager.remove_job(job.id)
        
        assert success
        assert job.id not in self.manager._jobs
        assert job.id not in self.manager._pending_jobs
    
    def test_clear_completed_jobs(self):
        job = Job(job_type="mock", input_file="test.stl")
        self.manager.add_job(job)
        
        self.manager.start_processing()
        time.sleep(0.2)  # Wait for completion
        
        count = self.manager.clear_completed_jobs()
        
        assert count == 1
        assert len(self.manager._completed_jobs) == 0
    
    def test_queue_summary(self):
        job1 = Job(job_type="mock", input_file="test1.stl")
        job2 = Job(job_type="mock", input_file="test2.stl")
        
        self.manager.add_job(job1)
        self.manager.add_job(job2)
        
        summary = self.manager.get_queue_summary()
        
        assert summary["total_jobs"] == 2
        assert summary["pending_jobs"] == 2
        assert summary["running_jobs"] == 0
        assert summary["completed_jobs"] == 0
        assert "session_id" in summary
        assert "timestamp" in summary
    
    def test_add_jobs_from_files(self):
        # Create mock STL files
        stl_files = []
        for i in range(3):
            stl_file = self.temp_dir / f"test{i}.stl"
            stl_file.write_text("mock stl content")
            stl_files.append(stl_file)
        
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()
        
        job_ids = self.manager.add_jobs_from_files(stl_files, output_dir)
        
        assert len(job_ids) == 3
        assert len(self.manager._pending_jobs) == 3
    
    def test_observers(self):
        state_events = []
        job_events = []
        
        def state_observer(summary):
            state_events.append(summary)
        
        def job_observer(event_type, job):
            job_events.append((event_type, job.id))
        
        self.manager.add_observer("state", state_observer)
        self.manager.add_observer("job", job_observer)
        
        job = Job(job_type="mock", input_file="test.stl")
        self.manager.add_job(job)
        
        self.manager.start_processing()
        time.sleep(0.2)  # Wait for completion
        
        assert len(state_events) > 0
        assert len(job_events) > 0
        assert any("job_added" in str(event) for event in job_events)


# Integration test
def test_full_processing_workflow():
    """Test complete job processing workflow."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create manager
        manager = EnhancedJobManager(
            max_workers=2,
            state_dir=temp_path,
            auto_save=False,
            enable_recovery=False
        )
        
        # Register mock executor
        executor = MockJobExecutor(execution_time=0.01)
        manager.execution_engine.register_executor("mock", executor)
        
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
                time.sleep(0.1)
            
            # Verify results
            final_summary = manager.get_queue_summary()
            assert final_summary["completed_jobs"] == 5
            assert final_summary["pending_jobs"] == 0
            assert final_summary["running_jobs"] == 0
            
            # Verify all jobs were executed
            assert len(executor.executions) == 5
            for job in jobs:
                assert job.status == JobStatus.COMPLETED
                assert job.id in executor.executions
        
        finally:
            manager.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])