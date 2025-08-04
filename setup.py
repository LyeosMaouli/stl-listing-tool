from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
if requirements_file.exists():
    with open(requirements_file, 'r') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
else:
    requirements = [
        'trimesh[easy]>=4.0.0',
        'numpy-stl>=3.0.0',
        'open3d>=0.19.0',
        'vtk>=9.2.0',
        'moviepy>=1.0.3',
        'Pillow>=10.0.0',
        'rq>=1.15.0',
        'redis>=4.5.0',
        'SQLAlchemy>=2.0.0',
        'click>=8.1.0',
        'pydantic>=2.0.0',
        'pytest>=7.4.0',
        'numpy>=1.21.0'
    ]

setup(
    name="stl-processor",
    version="0.1.0",
    author="Terragon Labs",
    author_email="dev@terragon.ai",
    description="STL file processing tool with ray-traced rendering, batch processing, and automated visualization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/terragon-labs/stl-listing-tool",
    packages=["stl_processor"] + ["stl_processor." + pkg for pkg in find_packages(where="src")],
    package_dir={"stl_processor": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Manufacturing",
        "Topic :: Multimedia :: Graphics :: 3D Rendering",
        "Topic :: Scientific/Engineering :: Visualization",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "gui": [
            "tkinterdnd2>=0.3.0",  # Drag and drop support for GUI
        ],
        "blender": [
            "bpy>=3.6.0",  # Blender Python API (when available)
        ],
        "gpu": [
            "cupy-cuda11x>=12.0.0",  # GPU acceleration (CUDA)
        ]
    },
    entry_points={
        "console_scripts": [
            "stl-processor=stl_processor.cli:cli",
            "stl-proc=stl_processor.cli:cli",  # Shorter alias
            "stl-gui=stl_processor.gui:main",  # GUI launcher
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yml", "*.yaml", "*.json", "*.txt"],
    },
    project_urls={
        "Bug Reports": "https://github.com/terragon-labs/stl-listing-tool/issues",
        "Source": "https://github.com/terragon-labs/stl-listing-tool",
        "Documentation": "https://github.com/terragon-labs/stl-listing-tool/docs",
    },
    keywords="stl 3d mesh processing rendering visualization batch miniatures",
    zip_safe=False,
)