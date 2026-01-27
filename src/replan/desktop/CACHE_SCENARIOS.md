# Working Image Cache Scenarios

This document lists all scenarios where the working image can change and how the cache is updated.

## Cache Structure
- Format: `(page_id, visibility_state, cached_image, mask_hashes)`
- `visibility_state`: `(should_hide_text, should_hide_hatching, should_hide_lines, page.tab_id)`
- `mask_hashes`: Dict with keys 'text', 'hatch', 'line' containing hash of each mask

## Scenarios Where Working Image Changes

### 1. Object Creation (Mask Addition)
**Scenarios:**
- `_add_manual_text_region()` - Adds text mask
- `_add_manual_hatch_region()` - Adds hatch mask  
- `_add_manual_line_region()` - Adds line mask
- `_add_text_regions_to_category()` - Adds multiple text masks from OCR
- `_create_object_from_mask()` - Creates objects from rectangle selection

**Cache Update:** 
- Incremental: Get old mask, update page mask, call `_update_working_image_cache_for_mask_with_old()`
- Method: Hide pixels in new mask areas

### 2. Object Deletion (Mask Removal)
**Scenarios:**
- `_delete_selected()` - Deletes objects and calls `_update_combined_*_mask()` with `force_recompute=True`
- `_remove_manual_text_region()` - Removes text region
- `_remove_manual_hatch_region()` - Removes hatch region
- `_remove_manual_line_region()` - Removes line region

**Cache Update:**
- Incremental: Get old mask BEFORE updating page, update page mask, call `_update_working_image_cache_for_mask_with_old()`
- Method: Restore pixels from original image for pixels in old mask but not in new mask

### 3. Object Modification (Mask Change)
**Scenarios:**
- When an object's mask is edited
- When merging objects (masks may change)

**Cache Update:**
- Same as deletion: Get old mask, compute new mask, update incrementally

### 4. Category Visibility Toggle
**Scenarios:**
- `_toggle_category_visibility()` - Changes what should be hidden

**Cache Update:**
- Invalidate cache (visibility state changes, can't incrementally update)

### 5. Page Switching
**Scenarios:**
- `_on_tab_changed()` - User clicks different tab
- `_switch_to_page()` - Programmatic page switch

**Cache Update:**
- Invalidate cache (different page/image)

### 6. Workspace Loading
**Scenarios:**
- `_load_workspace_from_path()` - Loads new workspace
- `_add_page()` - Adds new page

**Cache Update:**
- Invalidate cache (new pages/images)

### 7. Image Reloading
**Scenarios:**
- When original image is reloaded or changed

**Cache Update:**
- Invalidate cache (original image changed)

## Implementation Details

### Incremental Update Function
`_update_working_image_cache_for_mask_with_old(page, mask_type, new_mask, old_mask)`

**Handles:**
1. **Mask Removal**: Finds pixels in old_mask but not in new_mask, restores from `page.original_image`
2. **Mask Addition**: Hides pixels in new_mask by setting to white `[255, 255, 255]`
3. **Mask Update**: Combination of removal and addition

**Key Points:**
- Old mask must be retrieved BEFORE updating page's combined mask
- Only updates cache if it matches current page and visibility state
- Updates mask hash after applying changes

### Cache Invalidation
`_invalidate_working_image_cache()`

**Called when:**
- Page changes (different image)
- Visibility state changes (can't incrementally update)
- Workspace loaded (new pages)
- Image reloaded

## Code Locations

### Mask Addition
- `_add_manual_text_region()`: Line 2044-2060
- `_add_manual_hatch_region()`: Line 2074-2089
- `_add_manual_line_region()`: Line 2408-2420
- `_update_combined_text_mask()`: Line 2516-2521
- `_update_combined_hatch_mask()`: Line 2593-2603
- `_update_combined_line_mask()`: Line 2668-2679

### Mask Removal
- `_delete_selected()`: Line 4932-4941 (calls `_update_combined_*_mask` with force_recompute)
- `_remove_manual_text_region()`: Line 2632-2640
- `_remove_manual_hatch_region()`: Line 2652-2660

### Cache Invalidation
- `_add_page()`: Line 2753
- `_on_tab_changed()`: Line 2864
- `_switch_to_page()`: Line 4273
- `_load_workspace_from_path()`: Line 5272
- `_toggle_category_visibility()`: Line 841
