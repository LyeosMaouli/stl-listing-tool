# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the `stl-listing-tool` project, a Python-based STL file processing tool with ray-traced rendering, batch processing, and automated visualization features designed for creating professional listings of 3D models and miniatures.

## Current State

The project has core functionality implemented with **critical deployment issues now resolved** (August 2025):

**✅ CRITICAL FIXES IMPLEMENTED**:
- ✅ Setup.py entry points corrected - console commands now work after installation
- ✅ Import system standardized with proper package structure
- ✅ Configuration updated to modern Pydantic v2 API
- ✅ GUI dependencies handle graceful degradation

**Project Status**: Ready for installation and basic use. See `/docs/fixes/` directory for implementation details and remaining improvement opportunities.

### Implemented Components
- ✅ **Core STL Processing** (`src/core/`)
  - `stl_processor.py`: Main STL loading, validation, and dimension extraction
  - `dimension_extractor.py`: Advanced dimensional analysis and printability metrics  
  - `mesh_validator.py`: Comprehensive mesh validation and repair system

- ✅ **Rendering System** (`src/rendering/`)
  - `base_renderer.py`: Abstract renderer with material/lighting presets
  - `vtk_renderer.py`: VTK-based renderer for quick visualization

- ✅ **Configuration & Infrastructure**
  - `config/settings.py`: Pydantic-based configuration system
  - `src/utils/logger.py`: Structured logging with file/console output
  - `src/cli.py`: Click-based CLI interface

- ✅ **Testing & Packaging**
  - `tests/`: Comprehensive test suite with fixtures
  - `setup.py`: Package configuration with entry points
  - `requirements.txt`: Core dependencies

## Development Commands

### Installation

**✅ FIXED**: Critical installation issues have been resolved. Package is now ready for installation.
```bash
# Install package in development mode
pip install -e .

# Install with optional dependencies
pip install -e .[dev,gpu]

# Install dependencies only
pip install -r requirements.txt

# If you encounter package version conflicts, try minimal install:
pip install -r requirements-minimal.txt
```

**Installation Notes**:
- Console commands (stl-processor, stl-gui) now work correctly
- Import system uses proper package structure
- GUI gracefully handles missing tkinterdnd2 dependency
- Configuration system uses modern Pydantic v2 API

**Troubleshooting Installation:**
- If `open3d` version conflicts occur, the package uses `>=0.19.0` (latest available)
- If `vtk` causes issues on some systems, it's optional for basic STL processing
- Use `requirements-minimal.txt` for core functionality only
- Windows users may need Visual Studio C++ Build Tools for some packages

### Testing
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_stl_processor.py

# Run with coverage
pytest --cov=src
```

### CLI Usage

**✅ WORKING**: CLI commands now function correctly after installation.
```bash
# Analyze STL file
stl-processor analyze model.stl

# Validate mesh integrity
stl-processor validate model.stl --level standard --repair

# Render STL to image
stl-processor render model.stl output.png --material plastic --lighting studio

# Calculate scale information
stl-processor scale model.stl --height 28
```


## Architecture

### Technology Stack
- **Language**: Python 3.8+
- **Core Libraries**: trimesh, numpy-stl, open3d, vtk
- **Rendering**: VTK (implemented), Blender (planned)
- **CLI**: Click framework
- **Configuration**: Pydantic
- **Testing**: pytest
- **Queue System**: RQ + Redis (planned)

### Project Structure
```
stl_processor/
├── src/
│   ├── core/           # STL processing, validation, analysis
│   ├── rendering/      # Rendering engines (VTK, Blender)
│   ├── queue/          # Batch processing system (planned)
│   ├── generators/     # Video/image generation (planned)  
│   └── utils/          # Logging, configuration utilities
├── tests/              # Test suite with fixtures
├── config/             # Configuration files
├── data/               # Input/output/temp directories
├── docs/               # Documentation and development plans
└── scripts/            # Utility scripts
```

### Key Classes
- `STLProcessor`: Core STL loading and basic processing
- `DimensionExtractor`: Advanced dimensional analysis
- `MeshValidator`: Mesh integrity validation and repair
- `BaseRenderer`: Abstract renderer interface
- `VTKRenderer`: VTK-based rendering implementation

## Next Development Phases

### Phase 3: Batch Processing (In Progress)
- Implement pausable job manager
- RQ worker integration  
- Progress tracking and checkpointing

### Phase 4: Video & Image Generation
- 360° rotation video generator
- Color variation grid creator
- Professional size charts

### Phase 5: Advanced Rendering
- Blender integration for ray-tracing
- Material system expansion
- HDRI environment lighting

## Important Notes

- All STL files are processed defensively with comprehensive validation
- Rendering system supports multiple backends (VTK implemented, Blender planned)
- CLI interface follows Unix conventions with clear error handling
- Test coverage needs expansion (GUI and CLI not currently tested)
- Configuration system allows easy customization but needs Pydantic v2 update

**✅ RESOLVED**: Critical deployment issues have been fixed. See `/docs/fixes/` for:
- Complete implementation details of applied fixes
- Remaining improvement opportunities (high-priority items)
- Future enhancement roadmap
- Testing and validation procedures

## Development Guidelines

1. **Testing**: All new features require corresponding tests
2. **Documentation**: Update docstrings and this file for major changes
3. **Error Handling**: Use logging extensively and handle edge cases gracefully
4. **Performance**: Consider memory usage for large STL files
5. **Windows Compatibility**: Test on Windows as primary target platform