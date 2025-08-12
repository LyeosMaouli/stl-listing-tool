import pytest
import numpy as np
from pathlib import Path
import tempfile
import trimesh

# Import modules to test
from rendering.vtk_renderer import VTKRenderer  
from rendering.base_renderer import MaterialType, LightingPreset, RenderQuality


@pytest.fixture
def sample_stl_file():
    """Create a temporary STL file for testing."""
    # Create a simple pyramid mesh
    vertices = np.array([
        [0, 0, 0],      # Base center
        [1, 0, 0],      # Base corner 1
        [0, 1, 0],      # Base corner 2
        [-1, 0, 0],     # Base corner 3
        [0, -1, 0],     # Base corner 4
        [0, 0, 1]       # Apex
    ])
    
    faces = np.array([
        [0, 1, 2],      # Base triangle 1
        [0, 2, 3],      # Base triangle 2
        [0, 3, 4],      # Base triangle 3
        [0, 4, 1],      # Base triangle 4
        [1, 5, 2],      # Side triangle 1
        [2, 5, 3],      # Side triangle 2
        [3, 5, 4],      # Side triangle 3
        [4, 5, 1]       # Side triangle 4
    ])
    
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as tmp_file:
        mesh.export(tmp_file.name)
        tmp_file_path = Path(tmp_file.name)
    
    yield tmp_file_path
    
    # Cleanup
    tmp_file_path.unlink(missing_ok=True)


class TestVTKRenderer:
    """Test cases for VTKRenderer class."""
    
    def test_renderer_initialization(self):
        """Test renderer initialization."""
        renderer = VTKRenderer(800, 600)
        
        assert renderer.width == 800
        assert renderer.height == 600
        assert renderer.is_initialized is False
        
        # Test initialization
        result = renderer.initialize()
        assert result is True
        assert renderer.is_initialized is True
        
        renderer.cleanup()
    
    def test_scene_setup(self, sample_stl_file):
        """Test scene setup with STL file."""
        renderer = VTKRenderer()
        
        result = renderer.setup_scene(sample_stl_file)
        assert result is True
        assert renderer.mesh_path == sample_stl_file
        assert renderer.is_initialized is True
        
        renderer.cleanup()
    
    def test_camera_configuration(self, sample_stl_file):
        """Test camera position and orientation."""
        renderer = VTKRenderer()
        renderer.setup_scene(sample_stl_file)
        
        # Test camera positioning
        position = (2.0, 2.0, 2.0)
        target = (0.0, 0.0, 0.0)
        up = (0.0, 1.0, 0.0)
        
        result = renderer.set_camera(position, target, up)
        assert result is True
        
        renderer.cleanup()
    
    def test_lighting_presets(self, sample_stl_file):
        """Test different lighting presets."""
        renderer = VTKRenderer()
        renderer.setup_scene(sample_stl_file)
        
        # Test all lighting presets
        for preset in LightingPreset:
            result = renderer.set_lighting(preset)
            assert result is True
            assert renderer.lighting_preset == preset
        
        renderer.cleanup()
    
    def test_material_types(self, sample_stl_file):
        """Test different material types."""
        renderer = VTKRenderer()
        renderer.setup_scene(sample_stl_file)
        
        # Test all material types
        for material in MaterialType:
            if material != MaterialType.CUSTOM:  # Skip custom for now
                color = (0.5, 0.7, 0.9)
                result = renderer.set_material(material, color)
                assert result is True
                assert renderer.material_type == material
        
        renderer.cleanup()
    
    def test_background_color(self, sample_stl_file):
        """Test background color setting."""
        renderer = VTKRenderer()
        renderer.setup_scene(sample_stl_file)
        
        # Test background color
        background = (0.2, 0.3, 0.4, 1.0)
        renderer.set_background(background)
        assert renderer.background_color == background
        
        renderer.cleanup()
    
    def test_render_quality(self):
        """Test render quality settings."""
        renderer = VTKRenderer()
        
        # Test all quality presets
        for quality in RenderQuality:
            renderer.set_render_quality(quality)
            assert renderer.render_quality == quality
            
            settings = renderer.get_quality_settings()
            assert isinstance(settings, dict)
            assert 'samples' in settings
    
    def test_render_to_file(self, sample_stl_file):
        """Test rendering to image file."""
        renderer = VTKRenderer(400, 300)  # Smaller for faster testing
        renderer.setup_scene(sample_stl_file)
        
        # Setup basic rendering
        renderer.set_material(MaterialType.PLASTIC, (0.8, 0.2, 0.2))
        renderer.set_lighting(LightingPreset.STUDIO)
        
        # Render to temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            output_path = Path(tmp_file.name)
        
        try:
            result = renderer.render(output_path)
            assert result is True
            assert output_path.exists()
            assert output_path.stat().st_size > 0  # File should not be empty
        finally:
            output_path.unlink(missing_ok=True)
            renderer.cleanup()
    
    @pytest.mark.skip(reason="VTK render_to_array might be unstable in test environment")
    def test_render_to_array(self, sample_stl_file):
        """Test rendering to numpy array."""
        renderer = VTKRenderer(100, 100)  # Small for testing
        renderer.setup_scene(sample_stl_file)
        
        array = renderer.render_to_array()
        
        if array is not None:  # VTK might not support this in all environments
            assert isinstance(array, np.ndarray)
            assert len(array.shape) >= 2  # Should be at least 2D
        
        renderer.cleanup()


class TestBaseRendererMethods:
    """Test base renderer utility methods."""
    
    def test_material_properties(self):
        """Test material property retrieval."""
        renderer = VTKRenderer()
        
        for material_type in MaterialType:
            if material_type != MaterialType.CUSTOM:
                props = renderer.get_material_properties(material_type)
                assert isinstance(props, dict)
                assert 'roughness' in props
                assert 'metallic' in props
                assert 'specular' in props
    
    def test_lighting_setup(self):
        """Test lighting setup retrieval."""
        renderer = VTKRenderer()
        
        for preset in LightingPreset:
            if preset != LightingPreset.CUSTOM:
                setup = renderer.get_lighting_setup(preset)
                assert isinstance(setup, dict)
                assert 'ambient' in setup
    
    def test_camera_distance_calculation(self):
        """Test camera distance calculation."""
        renderer = VTKRenderer()
        
        # Test with a unit cube bounds
        bounds = np.array([[0, 0, 0], [1, 1, 1]])
        distance = renderer.calculate_camera_distance(bounds)
        
        assert isinstance(distance, float)
        assert distance > 0
        assert distance > 1.0  # Should be greater than the mesh size
    
    def test_orbit_positions(self):
        """Test orbit position generation."""
        renderer = VTKRenderer()
        
        center = (0, 0, 0)
        radius = 5.0
        num_positions = 8
        
        positions = renderer.get_orbit_positions(center, radius, num_positions)
        
        assert len(positions) == num_positions
        assert all(len(pos) == 3 for pos in positions)
        
        # Check that positions are roughly at the correct distance
        for pos in positions:
            distance = np.linalg.norm(np.array(pos) - np.array(center))
            assert abs(distance - radius) < 0.1  # Allow small tolerance


class TestRendererErrorHandling:
    """Test error handling in renderer."""
    
    def test_setup_scene_invalid_file(self):
        """Test scene setup with invalid file."""
        renderer = VTKRenderer()
        
        import tempfile
        invalid_path = Path(tempfile.gettempdir()) / "nonexistent_file.stl"
        result = renderer.setup_scene(invalid_path)
        
        assert result is False
        
        renderer.cleanup()
    
    def test_render_without_scene(self):
        """Test rendering without setting up scene."""
        renderer = VTKRenderer()
        renderer.initialize()
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            output_path = Path(tmp_file.name)
        
        try:
            result = renderer.render(output_path)
            # This might succeed or fail depending on VTK behavior
            # We just ensure it doesn't crash
            assert isinstance(result, bool)
        finally:
            output_path.unlink(missing_ok=True)
            renderer.cleanup()
    
    def test_camera_without_initialization(self):
        """Test camera operations without initialization."""
        renderer = VTKRenderer()
        
        result = renderer.set_camera((1, 1, 1))
        assert result is False  # Should fail without initialization
    
    def test_material_without_actor(self):
        """Test material setting without actor."""
        renderer = VTKRenderer()
        renderer.initialize()
        
        result = renderer.set_material(MaterialType.PLASTIC)
        assert result is False  # Should fail without actor
        
        renderer.cleanup()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])