import sys
sys.path.append('src')

from rendering.vtk_renderer import VTKRenderer
from pathlib import Path
import tempfile

# Test with a simple STL file path
stl_path = Path("./stls/AEGIS-Gladius2.stl")

print("=== RENDER DEBUG TEST ===")
renderer = VTKRenderer(1920, 1080)
print(f"1. Created renderer: {renderer.width}x{renderer.height}")

print("2. Initializing...")
renderer.initialize()
size = renderer.render_window.GetSize()
print(f"   After init: {size[0]}x{size[1]}")

print("3. Setting up scene...")
renderer.setup_scene(stl_path)
size = renderer.render_window.GetSize()
print(f"   After scene: {size[0]}x{size[1]}")

print("4. Rendering...")
with tempfile.NamedTemporaryFile(suffix='.png') as tmp:
    result = renderer.render(Path(tmp.name))
    size = renderer.render_window.GetSize()
    print(f"   After render: {size[0]}x{size[1]}")
    print(f"   Render result: {result}")

renderer.cleanup()