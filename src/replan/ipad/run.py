#!/usr/bin/env python3
"""
PlanMod iPad Segmenter - Run Script

This script handles the import path issues when running on iPad/Pyto.
Simply open this file in Pyto and tap the Play button.

Works on:
- Pyto (iOS)
- Pythonista (iOS)
- Desktop Python (for testing)
"""

import sys
import os

def setup_paths():
    """Set up Python paths for imports to work correctly."""
    # Get the directory containing this script
    if '__file__' in dir():
        script_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        # Fallback for some iOS environments
        script_dir = os.getcwd()
    
    # Add necessary paths
    paths_to_add = [
        script_dir,  # segmenter_ipad folder
        os.path.dirname(script_dir),  # tools folder
        os.path.dirname(os.path.dirname(script_dir)),  # PlanMod root
    ]
    
    for path in paths_to_add:
        if path and path not in sys.path:
            sys.path.insert(0, path)
    
    return script_dir

def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []
    
    try:
        import numpy
        print(f"  numpy: {numpy.__version__}")
    except ImportError:
        missing.append("numpy")
    
    try:
        from PIL import Image
        import PIL
        print(f"  Pillow: {PIL.__version__}")
    except ImportError:
        missing.append("Pillow")
    
    if missing:
        print()
        print("=" * 50)
        print("Missing dependencies!")
        print("Please install them in Pyto:")
        print()
        print("  1. Go to Pyto Settings (gear icon)")
        print("  2. Tap 'PyPI' or 'Install Package'")
        print("  3. Install:")
        for pkg in missing:
            print(f"     - {pkg}")
        print()
        print("Or in Pyto's terminal, run:")
        for pkg in missing:
            print(f"  pip install {pkg}")
        print()
        print("Then run this script again.")
        print("=" * 50)
        return False
    
    return True

def check_pyto_ui():
    """Check what Pyto UI features are available."""
    print()
    print("Checking Pyto UI availability...")
    
    try:
        import pyto_ui as ui
        print("  pyto_ui: Available")
        
        # Check specific features
        features = {
            'View': hasattr(ui, 'View'),
            'Label': hasattr(ui, 'Label'),
            'Button': hasattr(ui, 'Button'),
            'Color': hasattr(ui, 'Color'),
            'Font': hasattr(ui, 'Font'),
            'Alert': hasattr(ui, 'Alert'),
            'ImageView': hasattr(ui, 'ImageView'),
            'ScrollView': hasattr(ui, 'ScrollView'),
            'TextField': hasattr(ui, 'TextField'),
        }
        
        available = [k for k, v in features.items() if v]
        missing = [k for k, v in features.items() if not v]
        
        if available:
            print(f"  Available: {', '.join(available)}")
        if missing:
            print(f"  Missing: {', '.join(missing)}")
        
        # Check Color.rgb
        if hasattr(ui, 'Color'):
            if hasattr(ui.Color, 'rgb'):
                print("  Color.rgb: Available")
            else:
                print("  Color.rgb: Not available (will use hex)")
        
        # Check Font methods
        if hasattr(ui, 'Font'):
            font_methods = []
            if hasattr(ui.Font, 'system_font_of_size'):
                font_methods.append('system_font_of_size')
            if hasattr(ui.Font, 'bold_system_font_of_size'):
                font_methods.append('bold_system_font_of_size')
            if hasattr(ui.Font, 'systemFontOfSize'):
                font_methods.append('systemFontOfSize')
            if font_methods:
                print(f"  Font methods: {', '.join(font_methods)}")
        
        return True, ui
        
    except ImportError as e:
        print(f"  pyto_ui: Not available ({e})")
        return False, None

def create_simple_ui(app):
    """Create a simplified UI that works with basic Pyto features."""
    import pyto_ui as ui
    
    # Create main view
    main_view = ui.View()
    
    # Set background color (try different methods)
    try:
        main_view.background_color = ui.Color.rgb(0.15, 0.15, 0.16)
    except:
        try:
            main_view.background_color = ui.Color.hex("#262628")
        except:
            pass
    
    # Helper to create font
    def make_font(size, bold=False):
        try:
            if bold and hasattr(ui.Font, 'bold_system_font_of_size'):
                return ui.Font.bold_system_font_of_size(size)
            elif hasattr(ui.Font, 'system_font_of_size'):
                return ui.Font.system_font_of_size(size)
            elif hasattr(ui.Font, 'systemFontOfSize'):
                return ui.Font.systemFontOfSize(size)
        except:
            pass
        return None
    
    # Helper to create color
    def make_color(r, g, b):
        try:
            return ui.Color.rgb(r, g, b)
        except:
            try:
                # Convert to hex
                hex_color = "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))
                return ui.Color.hex(hex_color)
            except:
                return None
    
    # Title
    try:
        title = ui.Label("PlanMod Segmenter")
        title.frame = (20, 50, 300, 40)
        font = make_font(24, bold=True)
        if font:
            title.font = font
        color = make_color(1.0, 1.0, 1.0)
        if color:
            title.text_color = color
        main_view.add_subview(title)
    except Exception as e:
        print(f"Could not create title: {e}")
    
    # Status label
    try:
        status = ui.Label("Ready - Tap buttons below to get started")
        status.frame = (20, 100, 400, 30)
        font = make_font(14)
        if font:
            status.font = font
        color = make_color(0.7, 0.7, 0.7)
        if color:
            status.text_color = color
        main_view.add_subview(status)
        app._status_label = status
    except Exception as e:
        print(f"Could not create status: {e}")
    
    # Buttons
    button_configs = [
        ("Open Image", 150, lambda s: show_file_picker(app, "image")),
        ("Open PDF", 210, lambda s: show_file_picker(app, "pdf")),
        ("Open Workspace", 270, lambda s: show_file_picker(app, "workspace")),
        ("Save Workspace", 330, lambda s: save_workspace(app)),
        ("Console Mode", 410, lambda s: start_console(app)),
    ]
    
    for text, y, action in button_configs:
        try:
            btn = ui.Button()
            btn.title = text
            btn.frame = (20, y, 200, 44)
            btn.corner_radius = 8
            bg = make_color(0.2, 0.2, 0.22)
            if bg:
                btn.background_color = bg
            fg = make_color(0.0, 0.47, 1.0)
            if fg:
                btn.tint_color = fg
            btn.action = action
            main_view.add_subview(btn)
        except Exception as e:
            print(f"Could not create button '{text}': {e}")
    
    # Info text
    try:
        info = ui.Label("Categories: R=Rib, S=Spar, F=Former, B=Bulkhead, W=Wing, C=Custom")
        info.frame = (20, 480, 500, 30)
        font = make_font(12)
        if font:
            info.font = font
        color = make_color(0.5, 0.5, 0.5)
        if color:
            info.text_color = color
        main_view.add_subview(info)
    except Exception as e:
        print(f"Could not create info: {e}")
    
    return main_view

def show_file_picker(app, file_type):
    """Show file picker (uses Pyto's file picking if available)."""
    import pyto_ui as ui
    
    def update_status(msg):
        if hasattr(app, '_status_label'):
            app._status_label.text = msg
    
    try:
        # Try to use Pyto's file picker
        import file_picker
        
        if file_type == "image":
            types = ["public.image"]
        elif file_type == "pdf":
            types = ["com.adobe.pdf"]
        else:  # workspace
            types = ["public.json", "public.data"]
        
        path = file_picker.pick_file(types=types)
        
        if path:
            update_status(f"Loading: {os.path.basename(path)}")
            
            if file_type == "pdf":
                success = app.load_pdf(path)
            elif file_type == "workspace":
                success = app.load_workspace(path)
            else:
                success = app.load_image(path)
            
            if success:
                update_status(f"Loaded: {os.path.basename(path)}")
            else:
                update_status("Failed to load file")
        else:
            update_status("No file selected")
            
    except ImportError:
        # file_picker not available
        alert = ui.Alert("File Picker", 
                        "File picker not available.\n\n"
                        "Please use Console Mode to load files by path.")
        alert.add_action(ui.AlertAction("OK"))
        alert.show()
    except Exception as e:
        update_status(f"Error: {e}")

def save_workspace(app):
    """Save the current workspace."""
    import pyto_ui as ui
    
    def update_status(msg):
        if hasattr(app, '_status_label'):
            app._status_label.text = msg
    
    if not app.pages:
        update_status("No pages to save")
        return
    
    try:
        import file_picker
        path = file_picker.pick_save_file(
            default_name="workspace.pmw",
            types=["public.data"]
        )
        if path:
            if app.save_workspace(path):
                update_status(f"Saved: {os.path.basename(path)}")
            else:
                update_status("Failed to save")
    except ImportError:
        update_status("Save not available - use Console Mode")

def start_console(app):
    """Switch to console mode."""
    import pyto_ui as ui
    
    alert = ui.Alert("Console Mode", 
                    "Console mode will start in the terminal.\n\n"
                    "Use commands like:\n"
                    "  load <path>\n"
                    "  save <path>\n"
                    "  info\n"
                    "  quit")
    alert.add_action(ui.AlertAction("Start Console"))
    alert.show()
    
    # Run console in background
    run_console_mode(app)

def run_console_mode(app=None):
    """Run in console mode for testing."""
    print()
    print("=" * 50)
    print("PlanMod iPad Segmenter - Console Mode")
    print("=" * 50)
    print()
    print("Commands:")
    print("  load <path>   - Load an image or PDF")
    print("  save <path>   - Save workspace")
    print("  open <path>   - Open workspace")
    print("  info          - Show current state")
    print("  objects       - List objects")
    print("  categories    - List categories")
    print("  help          - Show this help")
    print("  quit          - Exit")
    print()
    
    # Try to create the app if not provided
    if app is None:
        try:
            try:
                from main import SegmenterApp
            except ImportError:
                from replan.ipad.main import SegmenterApp
            
            app = SegmenterApp()
            print("App initialized!")
            print(f"  Categories: {len(app.categories)}")
            print()
            
        except Exception as e:
            print(f"Could not initialize app: {e}")
            import traceback
            traceback.print_exc()
            return
    
    # Simple command loop
    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        
        if not cmd:
            continue
        
        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        if action in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
        elif action == "help":
            print("Commands: load, save, open, info, objects, categories, quit")
        elif action == "info":
            print(f"Pages: {len(app.pages)}")
            print(f"Objects: {len(app.all_objects)}")
            print(f"Categories: {len(app.categories)}")
            if app.current_page:
                print(f"Current: {app.current_page.display_name}")
        elif action == "objects":
            if not app.all_objects:
                print("No objects")
            for obj in app.all_objects:
                print(f"  {obj.name} ({obj.category}) - {len(obj.instances)} instance(s)")
        elif action == "categories":
            for key, cat in app.categories.items():
                vis = "visible" if cat.visible else "hidden"
                print(f"  {key}: {cat.full_name} ({vis})")
        elif action == "load":
            if arg:
                if arg.lower().endswith('.pdf'):
                    success = app.load_pdf(arg)
                else:
                    success = app.load_image(arg)
                print("Loaded!" if success else "Failed to load")
            else:
                print("Usage: load <filepath>")
        elif action == "save":
            if arg:
                success = app.save_workspace(arg)
                print("Saved!" if success else "Failed to save")
            else:
                print("Usage: save <filepath>")
        elif action == "open":
            if arg:
                success = app.load_workspace(arg)
                if success:
                    print(f"Opened! {len(app.pages)} pages, {len(app.all_objects)} objects")
                else:
                    print("Failed to open")
            else:
                print("Usage: open <filepath>")
        else:
            print(f"Unknown: {action} (type 'help' for commands)")

def run_app():
    """Run the iPad Segmenter app."""
    print("=" * 50)
    print("PlanMod iPad Segmenter")
    print("=" * 50)
    print()
    
    # Set up import paths
    script_dir = setup_paths()
    print(f"Script location: {script_dir}")
    print()
    
    # Check dependencies
    print("Checking dependencies...")
    if not check_dependencies():
        return
    print("  All dependencies OK!")
    
    # Check Pyto UI
    has_ui, ui = check_pyto_ui()
    
    if not has_ui:
        print()
        print("No UI available - starting console mode")
        run_console_mode()
        return
    
    # Try to create the app
    print()
    print("Initializing app...")
    try:
        try:
            from main import SegmenterApp
        except ImportError:
            from replan.ipad.main import SegmenterApp
        
        app = SegmenterApp()
        print(f"  App ready! ({len(app.categories)} categories)")
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("Falling back to console mode...")
        run_console_mode()
        return
    
    # Try to create UI
    print()
    print("Creating UI...")
    try:
        main_view = create_simple_ui(app)
        print("  UI created!")
        print()
        print("Launching app...")
        main_view.present()
        
    except Exception as e:
        print(f"  UI Error: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("Falling back to console mode...")
        run_console_mode(app)

# Entry point
if __name__ == "__main__":
    run_app()
