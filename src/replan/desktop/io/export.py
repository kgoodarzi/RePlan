"""Export functionality for images and data."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import cv2
import numpy as np

from replan.desktop.models import PageTab, DynamicCategory
from replan.desktop.core.rendering import Renderer


class ImageExporter:
    """Exports segmented images."""
    
    def __init__(self, renderer: Renderer = None):
        self.renderer = renderer or Renderer()
    
    def export_page(self,
                    path: str,
                    page: PageTab,
                    categories: Dict[str, DynamicCategory],
                    include_labels: bool = True) -> bool:
        """
        Export a segmented page as an image.
        
        Args:
            path: Output path
            page: Page to export
            categories: Category definitions
            include_labels: Whether to include labels
            
        Returns:
            True if successful
        """
        try:
            # Render at full resolution
            rendered = self.renderer.render_page(
                page, categories,
                zoom=1.0,
                show_labels=include_labels,
            )
            
            # Convert BGRA to BGR for saving
            if rendered.shape[2] == 4:
                rendered = cv2.cvtColor(rendered, cv2.COLOR_BGRA2BGR)
            
            cv2.imwrite(path, rendered)
            return True
            
        except Exception as e:
            print(f"Error exporting image: {e}")
            return False
    
    def export_masks(self,
                     output_dir: str,
                     page: PageTab,
                     separate_objects: bool = True) -> List[str]:
        """
        Export segmentation masks.
        
        Args:
            output_dir: Output directory
            page: Page to export
            separate_objects: Whether to create separate mask per object
            
        Returns:
            List of created file paths
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        created = []
        
        if page.original_image is None:
            return created
        
        h, w = page.original_image.shape[:2]
        
        if separate_objects:
            # One mask per object
            for obj in page.objects:
                mask = np.zeros((h, w), dtype=np.uint8)
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.mask is not None:
                            mask = np.maximum(mask, elem.mask)
                
                if np.any(mask):
                    filename = f"{page.model_name}_{page.page_name}_{obj.name}_mask.png"
                    filepath = out_path / filename
                    cv2.imwrite(str(filepath), mask)
                    created.append(str(filepath))
        else:
            # Single combined mask
            mask = np.zeros((h, w), dtype=np.uint8)
            for obj in page.objects:
                for inst in obj.instances:
                    for elem in inst.elements:
                        if elem.mask is not None:
                            mask = np.maximum(mask, elem.mask)
            
            filename = f"{page.model_name}_{page.page_name}_mask.png"
            filepath = out_path / filename
            cv2.imwrite(str(filepath), mask)
            created.append(str(filepath))
        
        return created


class DataExporter:
    """Exports segmentation data as JSON."""
    
    def export_page(self, path: str, page: PageTab) -> bool:
        """
        Export page data as JSON.
        
        Args:
            path: Output path
            page: Page to export
            
        Returns:
            True if successful
        """
        try:
            data = {
                "model": page.model_name,
                "page": page.page_name,
                "image_size": list(page.image_size) if page.image_size else None,
                "objects": [],
            }
            
            for obj in page.objects:
                obj_data = {
                    "id": obj.object_id,
                    "name": obj.name,
                    "category": obj.category,
                    "attributes": {
                        "material": obj.attributes.material,
                        "type": obj.attributes.obj_type,
                        "view": obj.attributes.view,
                        "size": {
                            "width": obj.attributes.width,
                            "height": obj.attributes.height,
                            "depth": obj.attributes.depth,
                        },
                        "description": obj.attributes.description,
                        "quantity": obj.attributes.quantity,
                    },
                    "instances": [],
                }
                
                for inst in obj.instances:
                    inst_data = {
                        "instance_num": inst.instance_num,
                        "view_type": inst.view_type,
                        "elements": [],
                    }
                    
                    for elem in inst.elements:
                        elem_data = {
                            "mode": elem.mode,
                            "points": elem.points,
                            "bounds": elem.bounds,
                            "centroid": elem.centroid,
                            "area": elem.area,
                        }
                        inst_data["elements"].append(elem_data)
                    
                    obj_data["instances"].append(inst_data)
                
                data["objects"].append(obj_data)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting data: {e}")
            return False
    
    def export_bom(self, path: str, pages: List[PageTab]) -> bool:
        """
        Export a Bill of Materials from all pages.
        
        Args:
            path: Output path
            pages: List of pages
            
        Returns:
            True if successful
        """
        try:
            bom = {
                "title": "Bill of Materials",
                "items": [],
            }
            
            # Collect unique objects
            seen = set()
            
            for page in pages:
                for obj in page.objects:
                    if obj.name in seen:
                        continue
                    seen.add(obj.name)
                    
                    item = {
                        "name": obj.name,
                        "category": obj.category,
                        "material": obj.attributes.material,
                        "type": obj.attributes.obj_type,
                        "quantity": obj.attributes.quantity,
                        "size": obj.attributes.size_string,
                        "description": obj.attributes.description,
                    }
                    bom["items"].append(item)
            
            # Sort by category then name
            bom["items"].sort(key=lambda x: (x["category"], x["name"]))
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(bom, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting BOM: {e}")
            return False


class InventoryExporter:
    """
    Exports comprehensive inventory/cut lists from nesting results.
    
    Generates shopping lists showing:
    - Sheet materials needed (count, sizes, total area)
    - Linear materials needed (stock count, lengths, total length)
    - Part placement details for cutting
    """
    
    def export_inventory(self, path: str,
                         sheet_results: Dict = None,
                         linear_results: Dict = None,
                         model_name: str = "") -> bool:
        """
        Export combined inventory from 2D and 1D nesting results.
        
        Args:
            path: Output file path
            sheet_results: Dict from NestingEngine.nest_by_material()
            linear_results: Dict from LinearNestingEngine.nest_by_width()
            model_name: Name of the model/project
            
        Returns:
            True if successful
        """
        try:
            inventory = {
                "title": f"Material Inventory - {model_name}" if model_name else "Material Inventory",
                "generated": datetime.now().isoformat(),
                "summary": {},
                "sheets": [],
                "linear_stock": [],
            }
            
            # Process sheet materials
            if sheet_results:
                sheet_summary = self._process_sheets(sheet_results, inventory["sheets"])
                inventory["summary"]["sheets"] = sheet_summary
            
            # Process linear materials
            if linear_results:
                linear_summary = self._process_linear(linear_results, inventory["linear_stock"])
                inventory["summary"]["linear"] = linear_summary
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(inventory, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting inventory: {e}")
            return False
    
    def _process_sheets(self, results: Dict, output: List) -> Dict:
        """Process 2D sheet nesting results."""
        total_sheets = 0
        total_area = 0.0
        materials_used = set()
        
        for group_key, sheets in results.items():
            for sheet in sheets:
                total_sheets += 1
                sheet_area = (sheet.width * sheet.height) / (96 * 96)  # Assume 96 DPI for sq inches
                total_area += sheet_area
                materials_used.add(sheet.material)
                
                sheet_data = {
                    "sheet_id": sheet.sheet_id,
                    "name": sheet.sheet_name or f"Sheet {total_sheets}",
                    "material": sheet.material,
                    "thickness": sheet.thickness,
                    "width_px": sheet.width,
                    "height_px": sheet.height,
                    "utilization": round(sheet.utilization, 1),
                    "parts": [
                        {
                            "name": part.name,
                            "x": part.x,
                            "y": part.y,
                            "width": part.width,
                            "height": part.height,
                            "rotated": part.rotated,
                        }
                        for part in sheet.parts
                    ],
                }
                output.append(sheet_data)
        
        return {
            "total_sheets": total_sheets,
            "total_area_sq_in": round(total_area, 2),
            "materials": list(materials_used),
        }
    
    def _process_linear(self, results: Dict, output: List) -> Dict:
        """Process 1D linear nesting results."""
        total_stock = 0
        total_length = 0.0
        total_waste = 0.0
        materials_used = set()
        
        for width, stocks in results.items():
            for stock in stocks:
                total_stock += 1
                total_length += stock.length
                total_waste += stock.waste
                materials_used.add(stock.material)
                
                stock_data = {
                    "stock_id": stock.stock_id,
                    "width": width,
                    "length": stock.length,
                    "material": stock.material,
                    "utilization": round(stock.utilization, 1),
                    "waste": round(stock.waste, 2),
                    "cuts": [
                        {
                            "part_name": p.part.name,
                            "position": p.position,
                            "length": p.part.length,
                            "copy": p.copy_num,
                        }
                        for p in sorted(stock.parts, key=lambda x: x.position)
                    ],
                }
                output.append(stock_data)
        
        return {
            "total_stock_pieces": total_stock,
            "total_length": round(total_length, 2),
            "total_waste": round(total_waste, 2),
            "utilization": round((total_length - total_waste) / total_length * 100, 1) if total_length > 0 else 0,
            "materials": list(materials_used),
        }
    
    def export_shopping_list(self, path: str,
                             sheet_results: Dict = None,
                             linear_results: Dict = None,
                             model_name: str = "") -> bool:
        """
        Export a simplified shopping list.
        
        Shows counts of materials needed without detailed placement info.
        
        Args:
            path: Output file path
            sheet_results: Dict from NestingEngine.nest_by_material()
            linear_results: Dict from LinearNestingEngine.nest_by_width()
            model_name: Name of the model/project
            
        Returns:
            True if successful
        """
        try:
            shopping = {
                "title": f"Shopping List - {model_name}" if model_name else "Shopping List",
                "generated": datetime.now().isoformat(),
                "sheets": [],
                "linear_stock": [],
            }
            
            # Aggregate sheets by material and size
            if sheet_results:
                sheet_counts = {}  # (material, thickness, w, h) -> count
                
                for group_key, sheets in sheet_results.items():
                    for sheet in sheets:
                        key = (sheet.material, sheet.thickness, sheet.width, sheet.height)
                        sheet_counts[key] = sheet_counts.get(key, 0) + 1
                
                for (material, thickness, w, h), count in sorted(sheet_counts.items()):
                    shopping["sheets"].append({
                        "material": material,
                        "thickness": thickness,
                        "width_px": w,
                        "height_px": h,
                        "quantity": count,
                    })
            
            # Aggregate linear stock by material and size
            if linear_results:
                stock_counts = {}  # (material, width, length) -> count
                
                for width, stocks in linear_results.items():
                    for stock in stocks:
                        key = (stock.material, width, stock.length)
                        stock_counts[key] = stock_counts.get(key, 0) + 1
                
                for (material, width, length), count in sorted(stock_counts.items()):
                    shopping["linear_stock"].append({
                        "material": material,
                        "width": width,
                        "length": length,
                        "quantity": count,
                    })
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(shopping, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting shopping list: {e}")
            return False
    
    def export_cut_list_text(self, path: str,
                             sheet_results: Dict = None,
                             linear_results: Dict = None,
                             model_name: str = "") -> bool:
        """
        Export a human-readable text cut list.
        
        Args:
            path: Output file path (.txt)
            sheet_results: Dict from NestingEngine.nest_by_material()
            linear_results: Dict from LinearNestingEngine.nest_by_width()
            model_name: Name of the model/project
            
        Returns:
            True if successful
        """
        try:
            lines = []
            lines.append(f"CUT LIST - {model_name}" if model_name else "CUT LIST")
            lines.append("=" * 60)
            lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            lines.append("")
            
            # Sheet materials
            if sheet_results:
                lines.append("SHEET MATERIALS")
                lines.append("-" * 40)
                
                for group_key, sheets in sheet_results.items():
                    for i, sheet in enumerate(sheets):
                        lines.append(f"\n{sheet.material} Sheet #{i+1}")
                        lines.append(f"  Size: {sheet.width} x {sheet.height} px")
                        lines.append(f"  Utilization: {sheet.utilization:.1f}%")
                        lines.append(f"  Parts:")
                        
                        for part in sheet.parts:
                            rot = " (rotated)" if part.rotated else ""
                            lines.append(f"    - {part.name}: {part.width}x{part.height} at ({part.x}, {part.y}){rot}")
                
                lines.append("")
            
            # Linear materials
            if linear_results:
                lines.append("LINEAR MATERIALS (STICKS/STRIPS)")
                lines.append("-" * 40)
                
                for width, stocks in linear_results.items():
                    lines.append(f"\nWidth: {width}")
                    
                    for i, stock in enumerate(stocks):
                        lines.append(f"\n  Stock #{i+1}: {stock.length} {stock.material}")
                        lines.append(f"    Utilization: {stock.utilization:.1f}%, Waste: {stock.waste:.2f}")
                        lines.append(f"    Cuts:")
                        
                        for part in sorted(stock.parts, key=lambda p: p.position):
                            lines.append(f"      {part.position:.2f}: {part.part.name} ({part.part.length})")
                
                lines.append("")
            
            lines.append("=" * 60)
            lines.append("END OF CUT LIST")
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            return True
            
        except Exception as e:
            print(f"Error exporting cut list: {e}")
            return False


