# RePlan - Feature Progress and Roadmap

**Project Status:** Brownfield Migration Complete  
**Version:** 6.0.0  
**Last Updated:** 2026-01-27

---

## Implemented Features (Current State)

### Core Functionality
- [x] Multi-mode segmentation tools
  - [x] Flood fill region selection
  - [x] Polygon/polyline drawing
  - [x] Freeform brush painting
  - [x] Line segment drawing
  - [x] Rectangular selection
  - [x] Select mode for existing objects
- [x] Object hierarchy system (Object -> Instance -> Element)
- [x] Category system with customizable colors
- [x] Dynamic category creation and management

### File Operations
- [x] Workspace save/load (.pmw format)
- [x] PDF import with page selection
- [x] Image import (PNG, JPG, JPEG)
- [x] JSON data export
- [x] PNG/image export with legends

### Analysis Tools
- [x] OCR-based label scanning (Tesseract)
- [x] Nesting/packing engine (rectpack)
- [x] Bill of materials generation

### User Interface
- [x] Dark/Light/High-contrast themes
- [x] VS Code/Cursor-inspired modern UI
- [x] Responsive layout with collapsible panels
- [x] Zoom and pan controls
- [x] Label visibility toggles
- [x] Object tree view with hierarchy
- [x] Status bar with context info

### Platform Support
- [x] Desktop (Windows, macOS, Linux) - tkinter
- [x] iPad/iOS (Pyto) - 92% feature parity

---

## Planned But Not Implemented

### High Priority

#### Auto-Detection Features
- [ ] **Auto text region detection** - Currently manual; needs CV-based automatic detection
- [ ] **Auto hatch region detection** - Currently manual; needs pattern recognition
- [ ] **Auto line region detection** - Currently manual; needs edge detection integration

#### Testing
- [ ] **Unit tests for all modules** - No automated tests currently
- [ ] **Integration tests** - End-to-end workflow testing
- [ ] **Performance regression tests** - Ensure operations stay under time targets

#### Performance Optimization
- [ ] **Profile all operations** - Add timing instrumentation
- [ ] **PDF loading optimization** - Target < 2 seconds for typical PDFs
- [ ] **Flood fill optimization** - Target < 1 second for typical regions
- [ ] **Canvas rendering optimization** - Smooth zoom/pan at any scale
- [ ] **Workspace save/load optimization** - Target < 1 second for complex workspaces

### Medium Priority

#### UI Enhancements
- [ ] **Advanced keyboard shortcuts** - Full keyboard navigation
- [ ] **Right-click context menus** - Quick actions on objects
- [ ] **Multi-window floating dialogs** - Detachable panels
- [ ] **Custom print dialogs** - Print preview and options
- [ ] **Undo/redo stack visualization** - History panel

#### Collaboration
- [ ] **WebSocket real-time collaboration** - Multiple users editing
- [ ] **Cloud workspace sync** - Auto-save to cloud storage
- [ ] **Version history** - Track workspace changes over time

#### Advanced Tools
- [ ] **Layer blending modes** - Overlay, multiply, etc.
- [ ] **Custom mask operations** - Boolean operations on masks
- [ ] **Measurement tools** - Ruler, angle measurement
- [ ] **Annotation tools** - Text notes, arrows, callouts

### Low Priority / Future Vision

#### Extended Platform Support
- [ ] **Mobile app beyond iPad** - Android, web
- [ ] **Browser-based version** - WebAssembly port

#### AI Integration
- [ ] **3D visualization preview** - Generate 3D model from 2D plans
- [ ] **Custom component training** - ML model for part recognition
- [ ] **Automatic component classification** - VLM-based recognition
- [ ] **Smart suggestions** - AI-assisted labeling

#### Manufacturing Integration
- [ ] **Assembly instructions generation** - Step-by-step guides
- [ ] **CAM integration** - Direct laser cutter/CNC output
- [ ] **Material optimization** - Minimize waste in nesting

---

## Known Limitations

### Technical Constraints
- DWG support requires external converter (ODA or LibreDWG)
- Large PDFs (>50MB) may cause memory issues on 8GB systems
- OCR accuracy varies with font quality and image resolution
- Complex cv2 operations not available on iOS (headless only)

### Platform-Specific Limitations

#### Desktop (tkinter)
- Single-threaded UI can freeze during heavy operations
- No native dark mode detection on older systems
- Limited high-DPI support on some platforms

#### iPad (Pyto)
- Background processing suspended by iOS
- File access through document picker only
- Limited keyboard shortcut support
- Vision OCR instead of Tesseract (different accuracy profile)

---

## Performance Targets

All operations should complete within these time limits:

| Operation | Target Time | Current Status |
|-----------|-------------|----------------|
| App startup | < 3 seconds | Not measured |
| PDF page load | < 2 seconds | Not measured |
| Flood fill | < 1 second | Not measured |
| Polygon mask | < 0.5 seconds | Not measured |
| Canvas render | < 0.1 seconds | Not measured |
| Workspace save | < 1 second | Not measured |
| Workspace load | < 2 seconds | Not measured |
| OCR scan (page) | < 5 seconds | Not measured |
| Nesting compute | < 3 seconds | Not measured |

---

## Migration Notes

### From PlanMod/tools/segmenter

This project was extracted from the PlanMod monorepo on 2026-01-27.

**Changes Made:**
- Renamed from "Segmenter" to "RePlan"
- Updated all imports from `tools.segmenter.*` to `replan.desktop.*`
- Updated config file path from `.planmod_segmenter.json` to `.replan.json`
- Class renamed from `SegmenterApp` to `RePlanApp`
- Added standalone project structure with pyproject.toml

**Source Documents:**
- `FEATURE_COMPARISON.md` - Desktop vs iPad feature parity
- `CACHE_SCENARIOS.md` - Working image cache documentation
- `MIGRATION_PROGRESS.md` - iPad migration tracking
- `segmenter_refactoring_plan.md` - Code architecture plan

---

## Issue Tracking

This project uses Beads for AI-friendly issue tracking.

Issues are stored in `.beads/` directory and synchronized via Git.

To view/manage issues with Cursor or Claude, the Beads MCP server is available.

---

## Contributing

See README.md for development setup and contribution guidelines.

Priority for contributions:
1. Performance profiling and optimization
2. Unit test coverage
3. Auto-detection features
4. UI enhancements
