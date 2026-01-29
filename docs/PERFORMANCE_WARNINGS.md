# Performance Warnings in Console Logs

This document catalogs all performance-related warnings and debug messages that may appear in the RePlan console logs.

## Automatic Performance Warnings (from PerformanceProfiler)

The `PerformanceProfiler` class automatically logs warnings when operations exceed their target times:

### Performance Targets

| Operation | Target | Warning Format |
|-----------|--------|----------------|
| `app_startup` | 3000ms | `Performance warning: app_startup took X.Xms (target: 3000ms)` |
| `pdf_load` | 2000ms | `Performance warning: pdf_load took X.Xms (target: 2000ms)` |
| `flood_fill` | 1000ms | `Performance warning: flood_fill took X.Xms (target: 1000ms)` |
| `polygon_mask` | 500ms | `Performance warning: polygon_mask took X.Xms (target: 500ms)` |
| `canvas_render` | 100ms | `Performance warning: canvas_render took X.Xms (target: 100ms)` |
| `workspace_save` | 1000ms | `Performance warning: workspace_save took X.Xms (target: 1000ms)` |
| `workspace_load` | 2000ms | `Performance warning: workspace_load took X.Xms (target: 2000ms)` |
| `ocr_scan` | 5000ms | `Performance warning: ocr_scan took X.Xms (target: 5000ms)` |
| `nesting_compute` | 3000ms | `Performance warning: nesting_compute took X.Xms (target: 3000ms)` |

**Location**: `src/replan/desktop/utils/profiling.py:100-103`

**Logging Level**: `logger.warning()` - appears in console when logging level is WARNING or above

## Manual Performance Debug Messages

### Mask Update Performance

**Location**: `src/replan/desktop/app.py:6657-6690`

- `DEBUG _delete_selected: Updating masks for {N} pages`
- `DEBUG _delete_selected: Mask update took {X.XXX} seconds`

These appear when deleting objects, especially mark_text/mark_hatch/mark_line objects that require mask recomputation.

### Memory-Related Warnings

**Location**: `src/replan/desktop/io/workspace.py`

1. **Memory errors during object loading** (line 250):
   ```
   Warning: Memory error loading object {object_id}: {error}
   ```

2. **General errors loading objects** (line 254):
   ```
   Warning: Error loading object {object_id}: {error}
   ```

3. **Failed mask decoding** (line 509):
   ```
   Warning: Failed to decode mask for element {element_id}: {error}
   ```

4. **Memory allocation failures** (line 526):
   ```
   Warning: Skipping element {element_id} - memory allocation failed
   ```

### Batch Processing Comments

**Location**: `src/replan/desktop/app.py`

- Line 2730-2739: Batch processing for text masks (100 masks per batch)
- Line 2813-2818: Batch processing for hatch masks (100 masks per batch)
- Line 373: Comment about manual regions being "slower - RLE decoding"

These don't produce warnings but indicate performance-conscious code paths.

## Performance Summary Output

**Location**: `src/replan/desktop/utils/profiling.py:149-175`

When `PerformanceProfiler.print_summary()` is called, it outputs:

```
PERFORMANCE SUMMARY
============================================================

{operation}: [OK] or [SLOW]
  Count: {N}
  Avg: {X.X}ms
  Min: {X.X}ms / Max: {X.X}ms
  Target: {X}ms
```

Operations marked `[SLOW]` indicate they're exceeding their targets.

## Other Performance-Related Messages

### Nesting Warnings

**Location**: `src/replan/desktop/core/nesting.py:616`

- `Warning: Part {name} ({length}) exceeds available stock`

This indicates a part is too long for available stock lengths, which may require special handling.

### Missing Library Warnings

**Location**: `src/replan/desktop/core/nesting.py:22`

- `Warning: rectpack not installed. Install with: pip install rectpack`

This affects nesting performance - without rectpack, 2D nesting won't work.

## How to View Performance Warnings

1. **Enable logging**: Set logging level to WARNING or above
2. **Check console output**: Performance warnings appear automatically when operations exceed targets
3. **Call profiler summary**: Use `PerformanceProfiler.get_instance().print_summary()` to see all timing data
4. **Save report**: Use `profiler.save_report(path)` to save timing data to JSON

## Performance Monitoring Recommendations

1. Monitor for `[SLOW]` markers in performance summaries
2. Watch for mask update times > 1 second (indicates many objects)
3. Check for memory warnings during workspace load (indicates large workspaces)
4. Monitor canvas_render times - should be < 100ms for smooth UI
