"""Dialog windows for the segmenter."""

from replan.desktop.dialogs.pdf_loader import PDFLoaderDialog
from replan.desktop.dialogs.label_scan import LabelScanDialog
from replan.desktop.dialogs.attributes import AttributeDialog
from replan.desktop.dialogs.settings import SettingsDialog
from replan.desktop.dialogs.rectangle_selection import RectangleSelectionDialog
from replan.desktop.dialogs.delete_object import DeleteObjectDialog
from replan.desktop.dialogs.page_selection import PageSelectionDialog
from replan.desktop.dialogs.nesting import NestingConfigDialog, SheetSize, MaterialGroup
from replan.desktop.dialogs.nesting_results import NestingResultsDialog
from replan.desktop.dialogs.transform import TransformDialog
from replan.desktop.dialogs.print_preview import PrintPreviewDialog

__all__ = [
    "PDFLoaderDialog",
    "LabelScanDialog",
    "AttributeDialog",
    "SettingsDialog",
    "RectangleSelectionDialog",
    "DeleteObjectDialog",
    "PageSelectionDialog",
    "NestingConfigDialog",
    "NestingResultsDialog",
    "TransformDialog",
    "PrintPreviewDialog",
    "SheetSize",
    "MaterialGroup",
]


