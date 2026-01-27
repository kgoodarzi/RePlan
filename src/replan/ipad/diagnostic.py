#!/usr/bin/env python3
"""
Pyto Diagnostic Script
Run this to see what features are available on your iPad.
Share the output to help debug issues.
"""

import sys
import os

print("=" * 50)
print("PYTO DIAGNOSTIC REPORT")
print("=" * 50)
print()

# Python version
print(f"Python Version: {sys.version}")
print(f"Platform: {sys.platform}")
print()

# Check basic modules
print("STANDARD MODULES:")
modules = ['os', 'sys', 'json', 'pathlib', 'dataclasses', 'typing']
for mod in modules:
    try:
        __import__(mod)
        print(f"  {mod}: ✓")
    except ImportError:
        print(f"  {mod}: ✗")
print()

# Check pip packages
print("PIP PACKAGES:")
packages = [
    ('numpy', 'numpy'),
    ('Pillow', 'PIL'),
    ('PyMuPDF', 'fitz'),
]
for name, import_name in packages:
    try:
        mod = __import__(import_name)
        ver = getattr(mod, '__version__', 'installed')
        print(f"  {name}: ✓ ({ver})")
    except ImportError:
        print(f"  {name}: ✗ (not installed)")
print()

# Check pyto_ui
print("PYTO_UI MODULE:")
try:
    import pyto_ui as ui
    print("  pyto_ui: ✓ imported")
    print()
    
    # List all available attributes
    all_attrs = [a for a in dir(ui) if not a.startswith('_')]
    print(f"  Available ({len(all_attrs)} items):")
    
    # Group by type
    classes = []
    functions = []
    constants = []
    
    for attr in all_attrs:
        obj = getattr(ui, attr)
        if isinstance(obj, type):
            classes.append(attr)
        elif callable(obj):
            functions.append(attr)
        else:
            constants.append(attr)
    
    if classes:
        print(f"    Classes: {', '.join(sorted(classes)[:20])}")
        if len(classes) > 20:
            print(f"             ... and {len(classes)-20} more")
    if functions:
        print(f"    Functions: {', '.join(sorted(functions)[:10])}")
    if constants:
        print(f"    Constants: {', '.join(sorted(constants)[:10])}")
    
    print()
    
    # Check specific UI elements we need
    print("  UI ELEMENTS WE NEED:")
    needed = ['View', 'Label', 'Button', 'Color', 'Font', 'Alert', 
              'ImageView', 'ScrollView', 'TextField', 'TableView']
    for elem in needed:
        has = hasattr(ui, elem)
        print(f"    {elem}: {'✓' if has else '✗'}")
    
    print()
    
    # Check Color methods
    print("  COLOR METHODS:")
    if hasattr(ui, 'Color'):
        color_methods = ['rgb', 'hex', 'white', 'black', 'red', 'blue', 'green', 
                        'clear', 'gray', 'systemBackground']
        for method in color_methods:
            has = hasattr(ui.Color, method)
            print(f"    Color.{method}: {'✓' if has else '✗'}")
    else:
        print("    Color class not available")
    
    print()
    
    # Check Font methods
    print("  FONT METHODS:")
    if hasattr(ui, 'Font'):
        font_methods = ['system_font_of_size', 'bold_system_font_of_size', 
                       'italic_system_font_of_size', 'systemFontOfSize',
                       'boldSystemFontOfSize', 'with_size']
        for method in font_methods:
            has = hasattr(ui.Font, method)
            print(f"    Font.{method}: {'✓' if has else '✗'}")
        
        # Try to list Font's actual methods
        font_attrs = [a for a in dir(ui.Font) if not a.startswith('_')]
        print(f"    Actual Font attributes: {', '.join(font_attrs[:15])}")
    else:
        print("    Font class not available")
    
    print()
    
    # Check View methods
    print("  VIEW METHODS:")
    if hasattr(ui, 'View'):
        view_attrs = [a for a in dir(ui.View) if not a.startswith('_')]
        print(f"    View attributes: {', '.join(view_attrs[:20])}")
    
    print()
    
    # Check Alert
    print("  ALERT:")
    if hasattr(ui, 'Alert'):
        alert_attrs = [a for a in dir(ui.Alert) if not a.startswith('_')]
        print(f"    Alert attributes: {', '.join(alert_attrs[:15])}")
        
        if hasattr(ui, 'AlertAction'):
            print("    AlertAction: ✓")
        else:
            print("    AlertAction: ✗")
            
        if hasattr(ui, 'AlertActionStyle'):
            print("    AlertActionStyle: ✓")
        else:
            print("    AlertActionStyle: ✗")
    
except ImportError as e:
    print(f"  pyto_ui: ✗ FAILED")
    print(f"  Error: {e}")

print()

# Check other Pyto modules
print("OTHER PYTO MODULES:")
pyto_modules = ['file_picker', 'photos', 'location', 'motion', 
                'notifications', 'speech', 'pasteboard', 'sharing']
for mod in pyto_modules:
    try:
        __import__(mod)
        print(f"  {mod}: ✓")
    except ImportError:
        print(f"  {mod}: ✗")

print()

# Check rubicon (for iOS native APIs)
print("RUBICON-OBJC (iOS Native Access):")
try:
    from rubicon.objc import ObjCClass
    print("  rubicon.objc: ✓")
    
    # Try to get UIScreen
    try:
        UIScreen = ObjCClass('UIScreen')
        main_screen = UIScreen.mainScreen
        bounds = main_screen.bounds
        print(f"  UIScreen: ✓")
        print(f"  Screen size: {bounds.size.width} x {bounds.size.height}")
    except Exception as e:
        print(f"  UIScreen: ✗ ({e})")
        
except ImportError as e:
    print(f"  rubicon.objc: ✗ ({e})")

print()

# Current working directory
print("FILESYSTEM:")
print(f"  Current dir: {os.getcwd()}")
print(f"  Home dir: {os.path.expanduser('~')}")
print(f"  Documents: {os.path.expanduser('~/Documents')}")

print()
print("=" * 50)
print("END OF DIAGNOSTIC REPORT")
print("=" * 50)
print()
print("Please copy all the text above and share it!")

