import pytest
import numpy as np
from pathlib import Path
import tempfile
import trimesh

# Import modules to test
from src.core.stl_processor import STLProcessor
from src.core.dimension_extractor import DimensionExtractor
from src.core.mesh_validator import MeshValidator, ValidationLevel


@pytest.fixture
def sample_stl_file():
    """Create a temporary STL file for testing."""
    # Create a simple cube mesh
    vertices = np.array([
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],  # Bottom face
        [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]   # Top face
    ])
    
    faces = np.array([
        [0, 1, 2], [0, 2, 3],  # Bottom
        [4, 7, 6], [4, 6, 5],  # Top
        [0, 4, 5], [0, 5, 1],  # Front
        [2, 6, 7], [2, 7, 3],  # Back
        [0, 3, 7], [0, 7, 4],  # Left
        [1, 5, 6], [1, 6, 2]   # Right
    ])
    
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as tmp_file:
        mesh.export(tmp_file.name)
        tmp_file_path = Path(tmp_file.name)
    
    yield tmp_file_path
    
    # Cleanup
    tmp_file_path.unlink(missing_ok=True)


@pytest.fixture
def invalid_stl_file():
    """Create a path to a non-existent STL file."""
    return Path("/tmp/nonexistent_file.stl")


class TestSTLProcessor:
    """Test cases for STLProcessor class."""
    
    def test_load_valid_stl(self, sample_stl_file):
        """Test loading a valid STL file."""
        processor = STLProcessor()
        result = processor.load(sample_stl_file)
        
        assert result is True
        assert processor.mesh is not None
        assert processor.filepath == sample_stl_file
    
    def test_load_invalid_file(self, invalid_stl_file):
        """Test loading a non-existent file."""
        processor = STLProcessor()
        result = processor.load(invalid_stl_file)
        
        assert result is False
        assert processor.mesh is None
    
    def test_validate_mesh(self, sample_stl_file):
        """Test mesh validation."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        result = processor.validate()
        assert result is True
    
    def test_get_dimensions(self, sample_stl_file):
        """Test dimension extraction."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        dimensions = processor.get_dimensions()
        
        assert isinstance(dimensions, dict)
        assert 'width' in dimensions
        assert 'height' in dimensions
        assert 'depth' in dimensions
        assert 'volume' in dimensions
        assert 'surface_area' in dimensions
        assert 'center' in dimensions
        
        # For a unit cube, dimensions should be close to 1
        assert abs(dimensions['width'] - 1.0) < 0.1
        assert abs(dimensions['height'] - 1.0) < 0.1
        assert abs(dimensions['depth'] - 1.0) < 0.1
    
    def test_get_scale_info(self, sample_stl_file):
        """Test scale information calculation."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        scale_info = processor.get_scale_info(target_height_mm=28.0)
        
        assert isinstance(scale_info, dict)
        assert 'scale_factor' in scale_info
        assert 'target_height_mm' in scale_info
        assert 'scaled_width' in scale_info
        assert scale_info['target_height_mm'] == 28.0
    
    def test_export_mesh(self, sample_stl_file):
        """Test mesh export functionality."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        with tempfile.NamedTemporaryFile(suffix='.obj', delete=False) as tmp_file:
            output_path = Path(tmp_file.name)
        
        try:
            result = processor.export_mesh(output_path)
            assert result is True
            assert output_path.exists()
        finally:
            output_path.unlink(missing_ok=True)


class TestDimensionExtractor:
    """Test cases for DimensionExtractor class."""
    
    def test_basic_dimensions(self, sample_stl_file):
        """Test basic dimension extraction."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        extractor = DimensionExtractor(processor.mesh)
        dimensions = extractor.get_basic_dimensions()
        
        assert isinstance(dimensions, dict)
        assert 'width' in dimensions
        assert 'diagonal' in dimensions
        assert 'bounding_box_volume' in dimensions
    
    def test_volume_analysis(self, sample_stl_file):
        """Test volume analysis."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        extractor = DimensionExtractor(processor.mesh)
        volume_info = extractor.get_volume_analysis()
        
        assert isinstance(volume_info, dict)
        assert 'volume' in volume_info
        assert 'surface_area' in volume_info
        assert 'volume_efficiency' in volume_info
        assert 'is_watertight' in volume_info
    
    def test_mesh_quality_metrics(self, sample_stl_file):
        """Test mesh quality analysis."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        extractor = DimensionExtractor(processor.mesh)
        quality = extractor.get_mesh_quality_metrics()
        
        assert isinstance(quality, dict)
        assert 'vertex_count' in quality
        assert 'face_count' in quality
        assert 'is_valid' in quality
        
        # For our cube, we should have 8 vertices and 12 faces
        assert quality['vertex_count'] == 8
        assert quality['face_count'] == 12
    
    def test_printability_analysis(self, sample_stl_file):
        """Test printability analysis."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        extractor = DimensionExtractor(processor.mesh)
        printability = extractor.get_printability_analysis()
        
        assert isinstance(printability, dict)
        assert 'estimated_layers' in printability
        assert 'stability_ratio' in printability
        assert 'is_stable_for_printing' in printability
        assert 'complexity_score' in printability
    
    def test_scale_recommendations(self, sample_stl_file):
        """Test scale recommendations."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        extractor = DimensionExtractor(processor.mesh)
        recommendations = extractor.get_scale_recommendations()
        
        assert isinstance(recommendations, dict)
        assert len(recommendations) > 0
        
        # Check that each recommendation has required fields
        for size_name, info in recommendations.items():
            assert 'scale_factor' in info
            assert 'scaled_width' in info
            assert 'scaled_height' in info
    
    def test_complete_analysis(self, sample_stl_file):
        """Test complete analysis function."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        extractor = DimensionExtractor(processor.mesh)
        analysis = extractor.get_complete_analysis()
        
        assert isinstance(analysis, dict)
        assert 'basic_dimensions' in analysis
        assert 'volume_analysis' in analysis
        assert 'mesh_quality' in analysis
        assert 'printability' in analysis
        assert 'scale_recommendations' in analysis


class TestMeshValidator:
    """Test cases for MeshValidator class."""
    
    def test_basic_validation(self, sample_stl_file):
        """Test basic mesh validation."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        validator = MeshValidator(processor.mesh)
        results = validator.validate(ValidationLevel.BASIC)
        
        assert isinstance(results, dict)
        assert 'is_valid' in results
        assert 'issues' in results
        assert 'validation_level' in results
        assert results['validation_level'] == 'basic'
    
    def test_standard_validation(self, sample_stl_file):
        """Test standard mesh validation."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        validator = MeshValidator(processor.mesh)
        results = validator.validate(ValidationLevel.STANDARD)
        
        assert isinstance(results, dict)
        assert results['validation_level'] == 'standard'
        # Our simple cube should be valid
        assert results['is_valid'] is True
    
    def test_strict_validation(self, sample_stl_file):
        """Test strict mesh validation."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        validator = MeshValidator(processor.mesh)
        results = validator.validate(ValidationLevel.STRICT)
        
        assert isinstance(results, dict)
        assert results['validation_level'] == 'strict'
    
    def test_repair_functionality(self, sample_stl_file):
        """Test mesh repair functionality."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        validator = MeshValidator(processor.mesh)
        repair_results = validator.repair(auto_fix=True)
        
        assert isinstance(repair_results, dict)
        assert 'repairs_applied' in repair_results
        assert 'repair_count' in repair_results
        assert 'post_repair_validation' in repair_results
    
    def test_validation_levels(self, sample_stl_file):
        """Test different validation levels."""
        processor = STLProcessor()
        processor.load(sample_stl_file)
        
        validator = MeshValidator(processor.mesh)
        
        # Test all validation levels
        for level in ValidationLevel:
            results = validator.validate(level)
            assert results['validation_level'] == level.value
            assert isinstance(results['issues'], list)


# Integration tests
class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_full_processing_pipeline(self, sample_stl_file):
        """Test the complete processing pipeline."""
        # Load and validate
        processor = STLProcessor()
        assert processor.load(sample_stl_file) is True
        
        # Validate mesh
        validator = MeshValidator(processor.mesh)
        validation_results = validator.validate()
        assert validation_results['is_valid'] is True
        
        # Extract dimensions
        extractor = DimensionExtractor(processor.mesh)
        analysis = extractor.get_complete_analysis()
        
        assert len(analysis) == 5  # Should have all analysis sections
        
        # Check that all components work together
        dimensions = processor.get_dimensions()
        basic_dims = analysis['basic_dimensions']
        
        # Dimensions should be consistent
        assert abs(dimensions['width'] - basic_dims['width']) < 0.001
        assert abs(dimensions['height'] - basic_dims['height']) < 0.001


if __name__ == '__main__':
    pytest.main([__file__, '-v'])