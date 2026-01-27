# RePlan

**Technical Drawing Annotation and Segmentation Tool**

RePlan is a professional-grade desktop application for annotating and segmenting model aircraft plans and technical drawings. It provides a modern, VS Code-inspired UI with powerful segmentation tools.

## Features

- Multi-mode segmentation (flood fill, polygon, freeform, line, rectangle)
- Category system with customizable colors
- Object hierarchy (Object -> Instance -> Element)
- PDF import with page selection
- OCR-based label scanning
- Nesting/packing engine for material optimization
- Dark/Light/High-contrast themes
- Responsive layout with collapsible panels
- Workspace save/load (.pmw format)

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourorg/replan.git
cd replan

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e .
```

### Requirements

- Python 3.10+
- Tesseract OCR (for label scanning)
- Poppler (for PDF processing)

## Usage

### Command Line

```bash
# Launch the application
replan

# Open a workspace file
replan --workspace path/to/workspace.pmw

# Open a PDF file
replan --pdf path/to/file.pdf
```

### As a Python Module

```bash
python -m replan.desktop
python -m replan.desktop --workspace path/to/workspace.pmw
python -m replan.desktop --pdf path/to/file.pdf
```

### Programmatically

```python
from replan.desktop import RePlanApp

app = RePlanApp()
app.run()
```

## Project Structure

```
RePlan/
├── src/
│   └── replan/
│       ├── desktop/      # Desktop tkinter application
│       ├── ipad/         # iPad/iOS version (Pyto)
│       └── findline/     # Line tracing tools
├── docs/
├── tests/
├── benchmarks/
└── .beads/               # Issue tracking for AI development
```

## Development

### Setup Development Environment

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Code Formatting

```bash
black src/
ruff check src/ --fix
```

### Issue Tracking with Beads

This project uses [Beads](https://github.com/steveyegge/beads) for AI-friendly issue tracking:

```bash
# Initialize beads (already done)
beads init

# List issues
beads list

# Add new issue
beads add "Description of issue" --priority high
```

## License

MIT License - See LICENSE file for details.

---

*Built for model aircraft builders and engineers*
