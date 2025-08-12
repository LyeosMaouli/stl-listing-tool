"""
Pytest configuration and shared fixtures.
"""
import pytest
from pathlib import Path

# Test configuration - imports handled by package structure


def pytest_configure(config):
    """Configure pytest settings."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "gpu: mark test as requiring GPU"
    )


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment."""
    # Ensure VTK runs in offscreen mode for testing
    try:
        import vtk
        # Force offscreen rendering for VTK in test environment
        vtk.vtkObject.GlobalWarningDisplayOff()
    except ImportError:
        pass  # VTK not available
    
    yield
    
    # Cleanup after tests
    pass


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory for tests."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir