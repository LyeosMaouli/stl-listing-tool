import vtk
import numpy as np
from pathlib import Path
from typing import Tuple, Optional

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .base_renderer import BaseRenderer, MaterialType, LightingPreset, RenderQuality
from ..utils.logger import logger

class VTKRenderer(BaseRenderer):
    """
    VTK-based renderer for quick STL visualization and rendering.
    """
    
    def __init__(self, width: int = 1920, height: int = 1080):
        super().__init__(width, height)
        
        # VTK components
        self.renderer = None
        self.render_window = None
        self.window_interactor = None
        self.mapper = None
        self.actor = None
        self.camera = None
        
        # Mesh data
        self.poly_data = None
        
    def initialize(self) -> bool:
        """Initialize VTK rendering system."""
        try:
            logger.info(f"Initializing VTK renderer with size: {self.width}x{self.height}")
            
            # Create renderer
            self.renderer = vtk.vtkRenderer()
            
            # Always set normal background - we'll handle compositing in post-processing
            self.renderer.SetBackground(*self.background_color[:3])
            
            # Create render window
            self.render_window = vtk.vtkRenderWindow()
            
            # Try different initialization approaches for better compatibility
            try:
                # Method 1: Standard off-screen rendering
                self.render_window.SetOffScreenRendering(1)
                self.render_window.SetSize(self.width, self.height)
                self.render_window.AddRenderer(self.renderer)
                self.render_window.Modified()
                
                # Test if the window size was set correctly
                test_size = self.render_window.GetSize()
                if test_size[0] != self.width or test_size[1] != self.height:
                    logger.warning(f"Initial size setting failed: got {test_size[0]}x{test_size[1]}, expected {self.width}x{self.height}")
                    
                    # Force size setting multiple times if needed
                    for attempt in range(3):
                        self.render_window.SetSize(self.width, self.height)
                        self.render_window.Modified()
                        current_size = self.render_window.GetSize()
                        if current_size[0] == self.width and current_size[1] == self.height:
                            logger.info(f"Window size set correctly on attempt {attempt + 1}")
                            break
                        logger.warning(f"Attempt {attempt + 1}: size still {current_size[0]}x{current_size[1]}")
                    
            except Exception as init_error:
                logger.error(f"Standard initialization failed: {init_error}, trying fallback")
                # Method 2: Fallback initialization
                self.render_window = vtk.vtkRenderWindow()
                self.render_window.AddRenderer(self.renderer)
                self.render_window.SetOffScreenRendering(1)
                self.render_window.SetSize(self.width, self.height)
                self.render_window.Modified()
            
            # Create camera
            self.camera = self.renderer.GetActiveCamera()
            
            # Final verification
            actual_size = self.render_window.GetSize()
            logger.info(f"VTK render window initialized with final size: {actual_size[0]}x{actual_size[1]}")
            
            if actual_size[0] != self.width or actual_size[1] != self.height:
                logger.error(f"CRITICAL: Window size verification failed! Expected {self.width}x{self.height}, got {actual_size[0]}x{actual_size[1]}")
                # Still mark as initialized but log the discrepancy
            
            self.is_initialized = True
            logger.info("VTK renderer initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize VTK renderer: {e}")
            return False
    
    def setup_scene(self, mesh_path: Path) -> bool:
        """Load STL file and setup scene."""
        try:
            if not self.is_initialized:
                if not self.initialize():
                    return False
            
            logger.info(f"Loading mesh from: {mesh_path}")
            
            # Load STL file
            reader = vtk.vtkSTLReader()
            reader.SetFileName(str(mesh_path))
            reader.Update()
            
            self.poly_data = reader.GetOutput()
            
            if self.poly_data.GetNumberOfPoints() == 0:
                logger.error("Loaded mesh has no points")
                return False
            
            # Create mapper
            self.mapper = vtk.vtkPolyDataMapper()
            self.mapper.SetInputData(self.poly_data)
            
            # Create actor
            self.actor = vtk.vtkActor()
            self.actor.SetMapper(self.mapper)
            
            # Add actor to renderer
            self.renderer.AddActor(self.actor)
            
            # Center mesh and set camera
            self._center_mesh()
            self._setup_default_camera()
            
            self.mesh_path = mesh_path
            logger.info("Scene setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup scene: {e}")
            return False
    
    def set_camera(self, 
                   position: Tuple[float, float, float],
                   target: Tuple[float, float, float] = (0, 0, 0),
                   up: Tuple[float, float, float] = (0, 1, 0)) -> bool:
        """Configure camera position and orientation."""
        try:
            if not self.camera:
                logger.error("Camera not initialized")
                return False
            
            self.camera.SetPosition(*position)
            self.camera.SetFocalPoint(*target)
            self.camera.SetViewUp(*up)
            
            logger.debug(f"Camera set to position: {position}, target: {target}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set camera: {e}")
            return False
    
    def set_lighting(self, preset: LightingPreset = LightingPreset.STUDIO) -> bool:
        """Setup lighting configuration."""
        try:
            if not self.renderer:
                logger.error("Renderer not initialized")
                return False
            
            # Remove existing lights
            lights = self.renderer.GetLights()
            lights.InitTraversal()
            light = lights.GetNextItem()
            while light:
                self.renderer.RemoveLight(light)
                light = lights.GetNextItem()
            
            lighting_config = self.get_lighting_setup(preset)
            
            # Add lights based on preset
            if preset == LightingPreset.STUDIO:
                self._add_studio_lighting(lighting_config)
            elif preset == LightingPreset.NATURAL:
                self._add_natural_lighting(lighting_config)
            elif preset == LightingPreset.DRAMATIC:
                self._add_dramatic_lighting(lighting_config)
            elif preset == LightingPreset.SOFT:
                self._add_soft_lighting(lighting_config)
            
            self.lighting_preset = preset
            logger.debug(f"Lighting set to: {preset.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set lighting: {e}")
            return False
    
    def set_material(self, 
                     material_type: MaterialType = MaterialType.PLASTIC,
                     color: Tuple[float, float, float] = (0.8, 0.8, 0.8),
                     **kwargs) -> bool:
        """Configure material properties."""
        try:
            if not self.actor:
                logger.error("Actor not initialized")
                return False
            
            property = self.actor.GetProperty()
            material_props = self.get_material_properties(material_type)
            
            # Set color
            property.SetColor(*color)
            
            # Set material properties
            property.SetSpecular(material_props.get('specular', 0.5))
            property.SetSpecularPower(100 * (1 - material_props.get('roughness', 0.3)))
            
            if material_props.get('metallic', 0.0) > 0.5:
                property.SetMetallic(1.0)
            else:
                property.SetMetallic(0.0)
            
            # Handle transparency for glass
            if material_type == MaterialType.GLASS:
                property.SetOpacity(0.7)
            
            self.material_type = material_type
            logger.debug(f"Material set to: {material_type.value} with color {color}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set material: {e}")
            return False
    
    def render(self, output_path: Path) -> bool:
        """Render scene to image file."""
        try:
            if not self.render_window:
                logger.error("Render window not initialized")
                return False
            
            logger.info(f"Rendering to: {output_path}")
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # If background image is set, render with compositing
            if self.has_background_image():
                return self._render_with_background(output_path)
            
            # Standard rendering without background image
            # Ensure render window size is set correctly before rendering
            self.render_window.SetSize(self.width, self.height)
            logger.debug(f"Set render window size to: {self.width} x {self.height}")
            
            # Render
            logger.critical(f"BEFORE RENDER: Window size = {self.render_window.GetSize()}")
            self.render_window.Render()
            logger.critical(f"AFTER RENDER: Window size = {self.render_window.GetSize()}")
            
            # Verify the actual window size after rendering
            actual_size = self.render_window.GetSize()
            logger.debug(f"Actual render window size after render: {actual_size[0]} x {actual_size[1]}")
            
            # Capture screenshot
            window_to_image = vtk.vtkWindowToImageFilter()
            window_to_image.SetInput(self.render_window)
            window_to_image.Update()
            
            # Write image
            if output_path.suffix.lower() == '.png':
                writer = vtk.vtkPNGWriter()
            elif output_path.suffix.lower() == '.jpg' or output_path.suffix.lower() == '.jpeg':
                writer = vtk.vtkJPEGWriter()
            else:
                # Default to PNG
                writer = vtk.vtkPNGWriter()
                output_path = output_path.with_suffix('.png')
            
            writer.SetFileName(str(output_path))
            writer.SetInputConnection(window_to_image.GetOutputPort())
            writer.Write()
            
            logger.info("Render completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to render: {e}")
            return False
    
    def render_to_array(self) -> Optional[np.ndarray]:
        """Render scene to numpy array."""
        try:
            if not self.render_window:
                logger.error("Render window not initialized")
                return None
            
            # Ensure render window size is set correctly before rendering
            self.render_window.SetSize(self.width, self.height)
            logger.debug(f"Set render window size to: {self.width} x {self.height}")
            
            # Render
            self.render_window.Render()
            
            # Verify the actual window size after rendering
            actual_size = self.render_window.GetSize()
            logger.debug(f"Actual render window size after render: {actual_size[0]} x {actual_size[1]}")
            
            # Capture to VTK image
            window_to_image = vtk.vtkWindowToImageFilter()
            window_to_image.SetInput(self.render_window)
            window_to_image.Update()
            
            # Convert to numpy array
            vtk_image = window_to_image.GetOutput()
            dims = vtk_image.GetDimensions()
            
            # Get image data as numpy array
            from vtk.util.numpy_support import vtk_to_numpy
            vtk_array = vtk_to_numpy(vtk_image.GetPointData().GetScalars())
            
            # Reshape and flip Y axis (VTK uses bottom-left origin)
            image_array = vtk_array.reshape(dims[1], dims[0], -1)
            image_array = np.flipud(image_array)
            
            return image_array
            
        except Exception as e:
            logger.error(f"Failed to render to array: {e}")
            return None
    
    def _center_mesh(self):
        """Center the mesh at origin."""
        if not self.poly_data:
            return
        
        # Get bounds
        bounds = self.poly_data.GetBounds()
        center = [
            (bounds[0] + bounds[1]) / 2,
            (bounds[2] + bounds[3]) / 2,
            (bounds[4] + bounds[5]) / 2
        ]
        
        # Create transform to center mesh
        transform = vtk.vtkTransform()
        transform.Translate(-center[0], -center[1], -center[2])
        
        # Apply transform
        transform_filter = vtk.vtkTransformPolyDataFilter()
        transform_filter.SetInputData(self.poly_data)
        transform_filter.SetTransform(transform)
        transform_filter.Update()
        
        self.poly_data = transform_filter.GetOutput()
        self.mapper.SetInputData(self.poly_data)
    
    def _setup_default_camera(self):
        """Setup default camera position."""
        if not self.poly_data or not self.camera:
            return
        
        # Calculate mesh bounds after centering
        bounds = self.poly_data.GetBounds()
        mesh_bounds = np.array([[bounds[0], bounds[2], bounds[4]], 
                               [bounds[1], bounds[3], bounds[5]]])
        
        # Calculate optimal camera distance
        distance = self.calculate_camera_distance(mesh_bounds)
        
        # Position camera
        self.camera.SetPosition(distance, distance * 0.5, distance * 0.5)
        self.camera.SetFocalPoint(0, 0, 0)
        self.camera.SetViewUp(0, 1, 0)
        
        # Reset camera to fit mesh
        self.renderer.ResetCamera()
        
        # Add some padding
        self.camera.Zoom(0.8)
    
    def _add_studio_lighting(self, config):
        """Add studio lighting setup."""
        # Key light
        key_light = vtk.vtkLight()
        key_light.SetPosition(*config['key_light']['position'])
        key_light.SetIntensity(config['key_light']['intensity'])
        key_light.SetColor(*config['key_light']['color'])
        self.renderer.AddLight(key_light)
        
        # Fill light
        fill_light = vtk.vtkLight()
        fill_light.SetPosition(*config['fill_light']['position'])
        fill_light.SetIntensity(config['fill_light']['intensity'])
        fill_light.SetColor(*config['fill_light']['color'])
        self.renderer.AddLight(fill_light)
        
        # Rim light
        rim_light = vtk.vtkLight()
        rim_light.SetPosition(*config['rim_light']['position'])
        rim_light.SetIntensity(config['rim_light']['intensity'])
        rim_light.SetColor(*config['rim_light']['color'])
        self.renderer.AddLight(rim_light)
        
        # Set ambient lighting
        self.renderer.SetAmbient(config['ambient'], config['ambient'], config['ambient'])
    
    def _add_natural_lighting(self, config):
        """Add natural lighting setup."""
        # Sun light
        sun_light = vtk.vtkLight()
        sun_light.SetPosition(*config['sun_light']['position'])
        sun_light.SetIntensity(config['sun_light']['intensity'])
        sun_light.SetColor(*config['sun_light']['color'])
        self.renderer.AddLight(sun_light)
        
        # Set ambient (sky light)
        ambient = config['ambient']
        self.renderer.SetAmbient(ambient, ambient, ambient)
    
    def _add_dramatic_lighting(self, config):
        """Add dramatic lighting setup."""
        # Key light
        key_light = vtk.vtkLight()
        key_light.SetPosition(*config['key_light']['position'])
        key_light.SetIntensity(config['key_light']['intensity'])
        key_light.SetColor(*config['key_light']['color'])
        self.renderer.AddLight(key_light)
        
        # Rim light
        rim_light = vtk.vtkLight()
        rim_light.SetPosition(*config['rim_light']['position'])
        rim_light.SetIntensity(config['rim_light']['intensity'])
        rim_light.SetColor(*config['rim_light']['color'])
        self.renderer.AddLight(rim_light)
        
        # Low ambient
        ambient = config['ambient']
        self.renderer.SetAmbient(ambient, ambient, ambient)
    
    def _add_soft_lighting(self, config):
        """Add soft lighting setup."""
        # Area light (simulated with multiple lights)
        for i in range(3):
            for j in range(3):
                light = vtk.vtkLight()
                pos = config['area_light']['position']
                offset_x = (i - 1) * 0.5
                offset_z = (j - 1) * 0.5
                light.SetPosition(pos[0] + offset_x, pos[1], pos[2] + offset_z)
                light.SetIntensity(config['area_light']['intensity'] / 9)
                light.SetColor(*config['area_light']['color'])
                self.renderer.AddLight(light)
        
        # Fill light
        fill_light = vtk.vtkLight()
        fill_light.SetPosition(*config['fill_light']['position'])
        fill_light.SetIntensity(config['fill_light']['intensity'])
        fill_light.SetColor(*config['fill_light']['color'])
        self.renderer.AddLight(fill_light)
        
        # High ambient
        ambient = config['ambient']
        self.renderer.SetAmbient(ambient, ambient, ambient)
    
    def _render_with_background(self, output_path: Path) -> bool:
        """Render with background image compositing using color-key masking."""
        try:
            if not PIL_AVAILABLE:
                logger.error("PIL/Pillow is required for background image support")
                return False
            
            logger.info("Rendering with background image compositing using masking")
            
            # Temporarily change background to a distinctive color for masking
            original_bg = self.background_color
            mask_color = (0.0, 1.0, 0.0)  # Bright green for masking
            self.renderer.SetBackground(*mask_color)
            
            try:
                # Render STL with mask color background
                rendered_array = self.render_to_array()
                if rendered_array is None:
                    logger.error("Failed to render STL to array")
                    return False
                
                logger.info(f"Rendered array shape: {rendered_array.shape}, dtype: {rendered_array.dtype}")
                
                # Create mask based on the green background
                # Convert to numpy array if needed
                if rendered_array.ndim == 3 and rendered_array.shape[2] >= 3:
                    # Create mask where pixels are close to the green background
                    green_mask = (
                        (rendered_array[:, :, 0] < 50) &  # Low red
                        (rendered_array[:, :, 1] > 200) &  # High green
                        (rendered_array[:, :, 2] < 50)     # Low blue
                    )
                    
                    logger.info(f"Created mask with {np.sum(green_mask)} green pixels out of {green_mask.size}")
                    
                    # Get background image resized to match render size
                    if self.background_image is not None:
                        background = self.background_image.copy()
                        if background.shape[:2] != rendered_array.shape[:2]:
                            bg_img = Image.fromarray(background)
                            bg_img = bg_img.resize((rendered_array.shape[1], rendered_array.shape[0]), Image.Resampling.LANCZOS)
                            background = np.array(bg_img)
                        
                        # Apply mask - replace green pixels with background
                        composited_array = rendered_array.copy()
                        composited_array[green_mask] = background[green_mask]
                        
                        logger.info("Successfully applied background mask")
                    else:
                        logger.error("Background image not available")
                        return False
                else:
                    logger.error(f"Unexpected rendered array shape: {rendered_array.shape}")
                    return False
                
            finally:
                # Restore original background color
                self.renderer.SetBackground(*original_bg[:3])
            
            # Save the composited image
            img = Image.fromarray(composited_array, 'RGB')
            
            # Handle different output formats
            if output_path.suffix.lower() in ['.jpg', '.jpeg']:
                img.save(output_path, 'JPEG', quality=95)
            elif output_path.suffix.lower() == '.png':
                img.save(output_path, 'PNG')
            else:
                # Default to PNG
                output_path = output_path.with_suffix('.png')
                img.save(output_path, 'PNG')
            
            logger.info(f"Background composited image saved to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to render with background: {e}")
            return False
    
    def cleanup(self):
        """Cleanup VTK resources."""
        super().cleanup()
        
        if self.render_window:
            self.render_window.Finalize()
        
        # Clear references
        self.renderer = None
        self.render_window = None
        self.window_interactor = None
        self.mapper = None
        self.actor = None
        self.camera = None
        self.poly_data = None