"""
RePlan Desktop v6.0

A modular, professional-grade tool for annotating and segmenting 
model aircraft plans and technical drawings.

Usage:
    python -m replan.desktop
    python -m replan.desktop --workspace path/to/workspace.pmw
    python -m replan.desktop --pdf path/to/file.pdf
    
Or:
    from replan.desktop import main
    main()
"""

import argparse

__version__ = "6.0.0"
__author__ = "RePlan Team"

from replan.desktop.app import RePlanApp


def main():
    """Launch the RePlan application with optional file to open."""
    parser = argparse.ArgumentParser(
        description="RePlan - Annotate and segment technical drawings"
    )
    parser.add_argument(
        "--workspace", "-w",
        type=str,
        help="Path to workspace file (.pmw) to open on startup"
    )
    parser.add_argument(
        "--pdf", "-p",
        type=str,
        help="Path to PDF file to open on startup"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"RePlan {__version__}"
    )
    
    args = parser.parse_args()
    
    app = RePlanApp(
        startup_workspace=args.workspace,
        startup_pdf=args.pdf
    )
    app.run()


__all__ = ["RePlanApp", "main", "__version__"]
