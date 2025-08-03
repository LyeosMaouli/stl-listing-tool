# STL Processing Tool Development Plan

## Project Overview
**Goal**: Build a Windows-compatible Python application for batch processing STL files with ray-traced rendering, video generation, and automated visualization features.

**Duration**: 10-12 weeks (2.5-3 months)  
**Team Size**: 1-2 developers

---

## Phase 1: Foundation & Core Architecture (Week 1-2)

### 1.1 Project Setup
- [ ] Initialize Git repository with proper .gitignore
- [ ] Create virtual environment and requirements.txt
- [ ] Set up project structure:
```
stl_processor/
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── stl_processor.py
│   │   ├── dimension_extractor.py
│   │   └── mesh_validator.py
│   ├── rendering/
│   │   ├── __init__.py
│   │   ├── base_renderer.py
│   │   ├── vtk_renderer.py
│   │   └── blender_renderer.py
│   ├── queue/
│   │   ├── __init__.py
│   │   ├── job_manager.py
│   │   └── pausable_worker.py
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── video_generator.py
│   │   ├── variation_generator.py
│   │   └── size_chart_generator.py
│   └── utils/
│       ├── __init__.py
│       ├── config.py
│       └── logger.py
├── tests/
├── data/
├── output/
├── config/
└── scripts/
```

### 1.2 Core Dependencies Installation
```python
# requirements.txt
trimesh[easy]==4.0.0
numpy-stl==3.0.0
open3d==0.17.0
vtk==9.2.0
moviepy==1.0.3
Pillow==10.0.0
rq==1.15.0
redis==4.5.0
SQLAlchemy==2.0.0
click==8.1.0
pydantic==2.0.0
pytest==7.4.0
```

### 1.3 Configuration System
```python
# config/settings.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Paths
    INPUT_DIR: str = "./data/input"
    OUTPUT_DIR: str = "./data/output"
    TEMP_DIR: str = "./data/temp"
    
    # Processing
    MAX_WORKERS: int = 4
    BATCH_SIZE: int = 10
    CHECKPOINT_INTERVAL: int = 5
    
    # Rendering
    RENDER_WIDTH: int = 1920
    RENDER_HEIGHT: int = 1080
    SAMPLES: int = 128
    
    # Queue
    REDIS_URL: str = "redis://localhost:6379"
    JOB_TIMEOUT: int = 3600
    
    class Config:
        env_file = ".env"
```

### Deliverables:
- Working project structure
- All dependencies installed and tested on Windows
- Basic configuration system
- Logging infrastructure

---

## Phase 2: STL Processing Core (Week 2-3)

### 2.1 STL File Handler
```python
# src/core/stl_processor.py
import trimesh
from pathlib import Path
from typing import Dict, Optional

class STLProcessor:
    def __init__(self):
        self.mesh: Optional[trimesh.Trimesh] = None
        
    def load(self, filepath: Path) -> bool:
        """Load STL file with validation"""
        try:
            self.mesh = trimesh.load(filepath)
            return self.validate()
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            return False
    
    def validate(self) -> bool:
        """Validate mesh integrity"""
        if not self.mesh.is_valid:
            self.mesh.fix_normals()
            self.mesh.remove_duplicate_faces()
            self.mesh.remove_degenerate_faces()
        return self.mesh.is_valid
    
    def get_dimensions(self) -> Dict[str, float]:
        """Extract accurate dimensions"""
        return {
            "width": float(self.mesh.extents[0]),
            "height": float(self.mesh.extents[1]),
            "depth": float(self.mesh.extents[2]),
            "volume": float(self.mesh.volume),
            "surface_area": float(self.mesh.area),
            "center": self.mesh.centroid.tolist()
        }
```

### 2.2 Dimension Extraction System
- Implement bounding box calculations
- Volume and surface area computation
- Center of mass detection
- Scale detection for miniatures

### 2.3 Mesh Optimization
- Implement decimation for large meshes
- Normal fixing and orientation
- Watertight mesh verification
- Performance benchmarking

### Deliverables:
- STL loading with both ASCII/binary support
- Dimension extraction accurate to 0.01mm
- Mesh validation and repair functionality
- Unit tests for all core functions

---

## Phase 3: Rendering System (Week 3-5)

### 3.1 Base Renderer Architecture
```python
# src/rendering/base_renderer.py
from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np

class BaseRenderer(ABC):
    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        
    @abstractmethod
    def setup_scene(self, mesh_path: Path):
        """Load mesh and setup scene"""
        pass
    
    @abstractmethod
    def set_camera(self, position, target, up):
        """Configure camera"""
        pass
    
    @abstractmethod
    def set_lighting(self, config: dict):
        """Setup lighting"""
        pass
    
    @abstractmethod
    def render(self, output_path: Path) -> np.ndarray:
        """Render scene to image"""
        pass
```

### 3.2 VTK Renderer (Quick Start)
- Implement VTK-based renderer for initial testing
- Basic material and lighting setup
- Camera positioning system
- Background customization

### 3.3 Blender Renderer (Production Quality)
```python
# scripts/blender_render.py
import bpy
import sys
from pathlib import Path

def setup_cycles():
    """Configure Cycles for ray tracing"""
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'GPU'
    bpy.context.scene.cycles.samples = 128
    
def import_stl(filepath):
    """Import STL and center in scene"""
    bpy.ops.import_mesh.stl(filepath=str(filepath))
    obj = bpy.context.active_object
    obj.location = (0, 0, 0)
    return obj
```

### 3.4 Material System
- Implement preset materials (plastic, metal, resin)
- Color variation system
- Texture mapping support
- Environment lighting (HDRI)

### Deliverables:
- Working VTK renderer
- Headless Blender integration
- Material preset library
- Render quality benchmarks

---

## Phase 4: Batch Processing & Queue System (Week 5-6)

### 4.1 Pausable Job Manager
```python
# src/queue/job_manager.py
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional
import pickle
from pathlib import Path

@dataclass
class JobState:
    id: str
    total_items: int
    processed_items: int
    current_item: Optional[str]
    status: str  # 'running', 'paused', 'stopped', 'completed'
    checkpoint_data: dict

class PausableJobManager:
    def __init__(self, checkpoint_dir: Path):
        self.jobs: Dict[str, JobState] = {}
        self.controls: Dict[str, Dict[str, threading.Event]] = {}
        self.checkpoint_dir = checkpoint_dir
        
    def create_job(self, job_id: str, items: List[Path]) -> JobState:
        """Create new pausable job"""
        state = JobState(
            id=job_id,
            total_items=len(items),
            processed_items=0,
            current_item=None,
            status='running',
            checkpoint_data={'items': items}
        )
        self.jobs[job_id] = state
        self.controls[job_id] = {
            'pause': threading.Event(),
            'stop': threading.Event()
        }
        self.controls[job_id]['pause'].set()  # Start unpaused
        return state
    
    def pause_job(self, job_id: str):
        """Pause job execution"""
        if job_id in self.controls:
            self.controls[job_id]['pause'].clear()
            self.jobs[job_id].status = 'paused'
            self.save_checkpoint(job_id)
```

### 4.2 Worker Implementation
- RQ worker with pause/resume support
- Progress tracking and reporting
- Error handling and retry logic
- Windows service compatibility

### 4.3 Queue Monitoring
- Real-time job status API
- Progress websocket updates
- Resource usage monitoring
- Queue health checks

### Deliverables:
- Pausable batch processing system
- Job persistence and recovery
- Progress tracking API
- Windows service wrapper

---

## Phase 5: Video & Image Generation (Week 6-8)

### 5.1 Rotation Video Generator
```python
# src/generators/video_generator.py
import numpy as np
from moviepy.editor import VideoClip
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

class RotationVideoGenerator:
    def __init__(self, mesh_path: Path, duration: int = 6):
        self.mesh = trimesh.load(mesh_path)
        self.duration = duration
        self.fps = 30
        
    def generate_frame(self, t: float) -> np.ndarray:
        """Generate single frame at time t"""
        angle = (t / self.duration) * 360
        
        # Render mesh at current angle
        scene = self.mesh.scene()
        scene.camera.look_at(
            points=[self.mesh.centroid],
            rotation=trimesh.transformations.rotation_matrix(
                np.radians(angle), [0, 1, 0]
            )
        )
        
        # Return frame as numpy array
        return scene.save_image(resolution=[1920, 1080], visible=False)
    
    def create_video(self, output_path: Path):
        """Generate rotation video"""
        clip = VideoClip(self.generate_frame, duration=self.duration)
        clip.write_videofile(str(output_path), fps=self.fps, codec='libx264')
```

### 5.2 Color Variation Generator
- Implement material color switching
- Grid layout composition
- Label and annotation system
- Batch rendering optimization

### 5.3 Size Chart Generator
```python
# src/generators/size_chart_generator.py
class SizeChartGenerator:
    def __init__(self, template_path: Path):
        self.template = Image.open(template_path)
        
    def create_chart(self, dimensions: dict, scales: dict) -> Image:
        """Generate size comparison chart"""
        # Create figure with dimensions
        # Add human silhouette for scale
        # Generate measurement callouts
        # Compose final image
        pass
```

### Deliverables:
- 360° rotation video generation
- Color variation grid creator
- Professional size charts
- Batch image processing

---

## Phase 6: User Interface (Week 8-9)

### 6.1 CLI Application
```python
# src/cli.py
import click
from pathlib import Path

@click.group()
def cli():
    """STL Processing Tool"""
    pass

@cli.command()
@click.argument('input_dir', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path())
@click.option('--workers', '-w', default=4)
@click.option('--preview', is_flag=True)
def process(input_dir, output, workers, preview):
    """Process STL files in batch"""
    pass

@cli.command()
@click.argument('job_id')
def pause(job_id):
    """Pause running job"""
    pass

@cli.command()
@click.argument('job_id')
def resume(job_id):
    """Resume paused job"""
    pass

@cli.command()
def status():
    """Show queue status"""
    pass
```

### 6.2 Configuration UI
- YAML/JSON configuration files
- Preset management system
- Template customization
- Output organization

### 6.3 Web Dashboard (Optional)
- Flask/FastAPI backend
- Real-time progress monitoring
- Preview generation
- Download management

### Deliverables:
- Full-featured CLI application
- Configuration file system
- Job monitoring tools
- Optional web interface

---

## Phase 7: Testing & Optimization (Week 9-10)

### 7.1 Test Suite Development
```python
# tests/test_stl_processor.py
import pytest
from pathlib import Path
from src.core.stl_processor import STLProcessor

@pytest.fixture
def sample_stl():
    return Path("tests/fixtures/sample.stl")

def test_load_stl(sample_stl):
    processor = STLProcessor()
    assert processor.load(sample_stl)
    assert processor.mesh is not None

def test_dimensions(sample_stl):
    processor = STLProcessor()
    processor.load(sample_stl)
    dims = processor.get_dimensions()
    assert all(k in dims for k in ['width', 'height', 'depth'])
```

### 7.2 Performance Optimization
- Memory profiling for large files
- Parallel processing optimization
- GPU acceleration testing
- Caching implementation

### 7.3 Windows-Specific Testing
- Path handling edge cases
- Service installation testing
- Multi-process compatibility
- File locking scenarios

### Deliverables:
- 90%+ test coverage
- Performance benchmarks
- Memory usage optimization
- Windows compatibility verification

---

## Phase 8: Deployment & Documentation (Week 10-12)

### 8.1 Packaging
```python
# setup.py
from setuptools import setup, find_packages

setup(
    name="stl-processor",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "stl-processor=cli:cli",
        ],
    },
)
```

### 8.2 Windows Installer
- PyInstaller executable creation
- NSIS installer script
- Service registration
- Start menu integration

### 8.3 Documentation
- User manual with examples
- API documentation
- Configuration guide
- Troubleshooting guide

### 8.4 Distribution
- GitHub releases
- Docker container (optional)
- Conda package (optional)
- Update mechanism

### Deliverables:
- Windows installer (.exe)
- Comprehensive documentation
- Example projects
- Update system

---

## Risk Mitigation

### Technical Risks
1. **Blender Integration Complexity**
   - Mitigation: Start with VTK, add Blender later
   - Fallback: Use only VTK/Open3D rendering

2. **Large File Memory Issues**
   - Mitigation: Implement streaming/chunking
   - Fallback: Set file size limits

3. **Windows Compatibility**
   - Mitigation: Test early and often on Windows
   - Fallback: WSL2 support documentation

### Schedule Risks
1. **Rendering Performance**
   - Buffer: 2 weeks allocated for optimization
   - Option: Reduce quality settings

2. **Feature Creep**
   - Define MVP clearly
   - Postpone nice-to-have features

---

## Success Metrics

### Performance Targets
- Process 100 STL files in < 30 minutes
- Generate 1080p renders in < 30 seconds
- Support files up to 1GB
- Memory usage < 4GB for typical operations

### Quality Targets
- Dimension accuracy within 0.1%
- Render quality comparable to commercial tools
- Zero data loss on pause/resume
- 99.9% job completion rate

### User Experience
- Single command batch processing
- Clear progress indication
- Intuitive configuration
- Comprehensive error messages

---

## Next Steps

1. **Week 1**: Set up development environment
2. **Week 1**: Create project repository
3. **Week 2**: Implement core STL processing
4. **Week 2**: Begin renderer research
5. **Daily**: Update progress tracking
6. **Weekly**: Team sync meetings (if applicable)

This plan provides a structured approach to building a professional STL processing tool while maintaining flexibility for adjustments based on discoveries during development.