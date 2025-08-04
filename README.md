# STL Listing Tool

⚠️ **PROJECT STATUS**: This project has critical deployment issues that must be fixed before use. See [/docs/fixes/](/docs/fixes/) for complete analysis and fix plans.

A comprehensive Python-based STL file processing tool with ray-traced rendering, batch processing, and automated visualization features designed for creating professional listings of 3D models and miniatures.

## Critical Issues Summary

**Installation Blockers:**
- Setup.py entry points incorrect - console commands won't work
- Import system inconsistencies throughout codebase
- Configuration uses deprecated Pydantic API  
- GUI dependencies cause silent failures

**Quick Status:**
- ✅ Core STL processing works
- ✅ Mesh validation and analysis works  
- ✅ VTK rendering works
- ❌ Package installation broken
- ❌ CLI commands don't work
- ❌ GUI has reliability issues

## For Developers

**Before working with this code:**

1. **Read the fix documentation**: `/docs/fixes/project-review-findings.md`
2. **Review the implementation plan**: `/docs/fixes/implementation-roadmap.md`  
3. **Check critical fixes**: `/docs/fixes/fix-plan-critical-issues.md`

**Estimated fix time**: 4-5 hours for critical issues, 2-3 weeks for complete resolution.

## Features (When Fixed)

- **Advanced STL Analysis**: Dimensional analysis, mesh validation, printability assessment
- **Professional Rendering**: Multiple material types, lighting presets, high-quality output
- **Batch Processing**: Automated workflows for multiple files
- **GUI Interface**: User-friendly drag-and-drop interface
- **CLI Tools**: Command-line interface for scripting and automation
- **Export Options**: Multiple output formats and scales

## Documentation

- **User Guide**: See [CLAUDE.md](CLAUDE.md) for detailed setup and usage
- **Architecture**: See [/docs/](/docs/) for technical documentation  
- **Fix Plans**: See [/docs/fixes/](/docs/fixes/) for current issues and solutions

## Contributing

**Current Priority**: Fix critical deployment issues before adding new features.

1. Review `/docs/fixes/` directory for current issues
2. Follow the implementation roadmap for systematic fixes
3. Ensure all fixes include corresponding tests
4. Update documentation as fixes are implemented

## License

[Add license information]

---

**⚠️ Do not attempt to install or deploy this package until critical fixes are implemented.**
