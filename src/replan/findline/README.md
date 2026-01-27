# Interactive Line Tracing Tool

An interactive tool for tracing leader lines in technical diagrams by clicking points on the image. The tool uses skeletonization and collision detection to accurately identify line segments and their intersections.

## Features

- **Interactive point selection**: Click points on the image to define line segments
- **Automatic line tracing**: Traces lines along the skeleton between user-selected points
- **Collision detection**: Automatically detects and handles intersections with other objects
- **Zoom and pan controls**: 
  - `+` button: Zoom in
  - `-` button: Zoom out
  - `Fit` button: Fit image to viewport
  - Scrollbars: Pan when zoomed in
- **Real-time visualization**: See traced lines and mask outlines in real-time
- **Multiple line support**: Trace multiple lines sequentially

## Requirements

- Python 3.7+
- opencv-python>=4.8.0
- numpy>=1.24.0
- scikit-image>=0.21.0

Install dependencies:
```bash
pip install opencv-python numpy scikit-image
```

## Usage

### Interactive Mode

```bash
python trace_interactive.py <image_path>
```

Example:
```bash
python trace_interactive.py IMG_9236_No_Text.jpg
```

### Command Line Mode (Non-Interactive)

```bash
python trace_with_points.py <image_path> --points "x1,y1 x2,y2 x3,y3"
```

Example:
```bash
python trace_with_points.py IMG_9236_No_Text.jpg --points "172,209 253,210 420,758"
```

## Controls

### Interactive Mode Controls

- **Left Click**: Add point to current line
- **`+` Button**: Zoom in
- **`-` Button**: Zoom out
- **`Fit` Button**: Reset zoom and fit image to viewport
- **Scrollbars**: Pan the image (appear when zoomed in)
- **`c` Key**: Clear current points (start new line)
- **`r` Key**: Reset all lines
- **`s` Key**: Save results
- **`q` Key**: Quit

## Output

The tool generates:

1. **Visualization image**: Shows traced lines with:
   - Red contours: Mask outline of detected lines
   - Cyan line: Thin center traced path
   - Green circles: User-selected points

2. **Mask files**: Binary masks for each traced line

3. **Combined mask**: Combined mask of all traced lines

## How It Works

1. **Preprocessing**: Converts image to monochrome and skeletonizes it
2. **Point Selection**: User clicks points to define line segments
3. **Skeleton Matching**: Finds nearest skeleton points to user points
4. **Line Tracing**: Traces path along skeleton between points
5. **Thickness Measurement**: Measures line thickness from original image
6. **Collision Detection**: Detects intersections using skeleton junctions
7. **Mask Creation**: Creates mask with exclusion zones at intersections

## Algorithm Details

- Uses skeletonization to find line center paths
- Detects collisions using skeleton junctions (points with 3+ neighbors)
- Creates exclusion zones at intersections to split lines
- Handles lines crossing other objects from underneath

## Notes

- The tool assumes lines cross other objects from underneath
- Intersections are detected automatically using skeleton analysis
- Zoom and pan are synchronized for both axes
- The control panel (buttons) is not affected by zoom
