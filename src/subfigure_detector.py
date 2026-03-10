"""
TrustMed-AI Subfigure Detection Module
=======================================
Detects compound medical figures (multi-panel images) and splits them
into individual subfigures for independent analysis and retrieval.

Inspired by: MedICaT (Subramanian et al., EMNLP 2020)
Uses OpenCV + PIL heuristics — no model downloads required.

Usage:
    from src.subfigure_detector import detect_compound_figure, split_compound_figure

    analysis = detect_compound_figure("path/to/image.jpg")
    if analysis.is_compound:
        subfigures = split_compound_figure("path/to/image.jpg")
        for sf in subfigures:
            print(f"Panel {sf.panel_id}: {sf.bbox}")
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
from enum import Enum

import cv2
import numpy as np
from PIL import Image


# ─── Configuration ───────────────────────────────────────────────────────────

# Minimum panel dimensions (pixels)
MIN_PANEL_WIDTH = 80
MIN_PANEL_HEIGHT = 80

# White-space / border detection
WHITE_THRESHOLD = 230          # Pixel value above this is "white/light"
MIN_SEPARATOR_RATIO = 0.7      # Separator must span at least 70% of image dim (was 0.5)
MIN_SEPARATOR_THICKNESS = 4    # Minimum pixels for a separator line
MAX_SEPARATOR_THICKNESS = 60   # Maximum border width

# Panel validation
MIN_PANEL_ASPECT_RATIO = 0.3   # Panel width/height (or height/width) must be >= 0.3
MAX_SIZE_RATIO = 2.5           # Largest panel can be at most 2.5x the smallest panel area
SIZE_VARIANCE_TOLERANCE = 0.35 # ±35% variance in panel sizes allowed

# Confidence thresholds
MIN_COMPOUND_CONFIDENCE = 0.6  # Must be >= 0.6 to trigger (was 0.5)
MIN_PANEL_AREA_RATIO = 0.05   # Each panel must be >= 5% of total image area

# Edge margin: separators within this % of image edge are likely borders, not dividers
EDGE_MARGIN_RATIO = 0.08      # Ignore separators in first/last 8% of image


# ─── Data Classes ────────────────────────────────────────────────────────────

class PanelLayout(Enum):
    SINGLE = "single"
    GRID_1x2 = "1x2"
    GRID_1x3 = "1x3"
    GRID_1x4 = "1x4"
    GRID_2x1 = "2x1"
    GRID_2x2 = "2x2"
    GRID_2x3 = "2x3"
    GRID_3x1 = "3x1"
    GRID_3x2 = "3x2"
    GRID_3x3 = "3x3"
    IRREGULAR = "irregular"


@dataclass
class BoundingBox:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center(self) -> Tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    @property
    def aspect_ratio(self) -> float:
        """Returns ratio of shorter side to longer side (always 0-1)."""
        if self.width == 0 or self.height == 0:
            return 0.0
        return min(self.width, self.height) / max(self.width, self.height)


@dataclass
class SubfigureData:
    image: Image.Image
    bbox: BoundingBox
    panel_id: str           # "A", "B", "C" or "panel_0", "panel_1"
    label: Optional[str]    # Detected text label (if any)
    position: int           # Sequential index (0, 1, 2, ...)
    grid_position: Tuple[int, int]  # (row, col)
    confidence: float       # Detection confidence for this panel


@dataclass
class CompoundFigureAnalysis:
    is_compound: bool
    confidence: float
    num_panels: int
    panel_positions: List[BoundingBox]
    detected_labels: List[str]
    grid_structure: Optional[Tuple[int, int]]  # (rows, cols) or None
    layout: PanelLayout


# ─── Internal Detection Functions ────────────────────────────────────────────

def _find_separators(gray: np.ndarray, axis: int) -> List[Tuple[int, int]]:
    """
    Find white-space separator lines along an axis.
    Only considers separators that are INTERNAL to the image (not at edges).

    Args:
        gray: Grayscale image as numpy array
        axis: 0 for horizontal separators (rows), 1 for vertical separators (cols)

    Returns:
        List of (start, end) positions of detected separators
    """
    h, w = gray.shape

    if axis == 0:
        scan_dim = h
        cross_dim = w
    else:
        scan_dim = w
        cross_dim = h

    # Edge margin: ignore separators too close to the edges
    edge_margin = int(scan_dim * EDGE_MARGIN_RATIO)

    separators = []
    in_separator = False
    sep_start = 0

    for i in range(scan_dim):
        if axis == 0:
            line = gray[i, :]
        else:
            line = gray[:, i]

        white_fraction = np.mean(line > WHITE_THRESHOLD)

        if white_fraction >= MIN_SEPARATOR_RATIO:
            if not in_separator:
                sep_start = i
                in_separator = True
        else:
            if in_separator:
                sep_end = i
                thickness = sep_end - sep_start
                # Only accept if: correct thickness AND not at the edge
                sep_center = (sep_start + sep_end) // 2
                is_internal = edge_margin < sep_center < (scan_dim - edge_margin)
                if MIN_SEPARATOR_THICKNESS <= thickness <= MAX_SEPARATOR_THICKNESS and is_internal:
                    separators.append((sep_start, sep_end))
                in_separator = False

    # Handle separator at the very end — these are edge borders, skip them
    # (We intentionally don't add trailing separators since they're likely image borders)

    return separators


def _separators_to_splits(
    separators: List[Tuple[int, int]],
    total_size: int
) -> List[Tuple[int, int]]:
    """
    Convert separator positions to panel region boundaries.

    Given separators at positions [(s1_start, s1_end), (s2_start, s2_end), ...],
    compute the panel regions between them.

    Returns:
        List of (region_start, region_end) for each panel along this axis
    """
    if not separators:
        return [(0, total_size)]

    regions = []

    # Region before first separator
    first_sep_start = separators[0][0]
    if first_sep_start > MIN_PANEL_WIDTH:
        regions.append((0, first_sep_start))

    # Regions between separators
    for i in range(len(separators) - 1):
        region_start = separators[i][1]      # End of current separator
        region_end = separators[i + 1][0]    # Start of next separator
        if region_end - region_start > MIN_PANEL_WIDTH:
            regions.append((region_start, region_end))

    # Region after last separator
    last_sep_end = separators[-1][1]
    if total_size - last_sep_end > MIN_PANEL_WIDTH:
        regions.append((last_sep_end, total_size))

    return regions


def _infer_grid(
    h_regions: List[Tuple[int, int]],
    v_regions: List[Tuple[int, int]]
) -> Tuple[int, int]:
    """Infer grid structure from horizontal and vertical regions."""
    rows = len(h_regions)
    cols = len(v_regions)
    return (rows, cols)


def _validate_panels(
    panels: List[BoundingBox],
    image_area: int
) -> List[BoundingBox]:
    """Filter out panels that are too small, too large, or have bad aspect ratios."""
    valid = []
    for panel in panels:
        area_ratio = panel.area / image_area
        if area_ratio < MIN_PANEL_AREA_RATIO or area_ratio > 0.95:
            continue
        if panel.width < MIN_PANEL_WIDTH or panel.height < MIN_PANEL_HEIGHT:
            continue
        # Reject absurdly narrow or tall panels
        if panel.aspect_ratio < MIN_PANEL_ASPECT_RATIO:
            continue
        valid.append(panel)
    return valid


def _check_size_consistency(panels: List[BoundingBox]) -> bool:
    """
    Check if panels are roughly consistent in size.
    Rejects splits where the largest panel is much bigger than the smallest.
    """
    if len(panels) < 2:
        return True
    areas = [p.area for p in panels]
    max_area = max(areas)
    min_area = min(areas)
    if min_area <= 0:
        return False
    ratio = max_area / min_area
    return ratio <= MAX_SIZE_RATIO


def _compute_confidence(
    panels: List[BoundingBox],
    grid: Tuple[int, int],
    image_size: Tuple[int, int]
) -> float:
    """
    Compute confidence score for compound figure detection.

    Higher confidence for:
    - Regular grid layouts (2x2, 2x3, etc.)
    - Consistent panel sizes
    - Multiple panels (2+)
    - Good aspect ratios on all panels
    """
    if len(panels) < 2:
        return 0.0

    confidence = 0.0

    # Base score from grid match
    n_panels = len(panels)
    expected_panels = grid[0] * grid[1]

    if n_panels == expected_panels:
        confidence += 0.3
    elif abs(n_panels - expected_panels) <= 1:
        confidence += 0.15
    else:
        confidence += 0.05

    # Size consistency score (most important factor)
    areas = [p.area for p in panels]
    mean_area = np.mean(areas)
    if mean_area > 0:
        area_cv = np.std(areas) / mean_area  # Coefficient of variation
        if area_cv < 0.1:
            confidence += 0.35  # Very consistent — strong signal
        elif area_cv < 0.2:
            confidence += 0.25
        elif area_cv < 0.3:
            confidence += 0.1
        else:
            confidence -= 0.15  # PENALIZE wildly inconsistent panels

    # Max-to-min size ratio check
    max_area = max(areas)
    min_area = min(areas) if min(areas) > 0 else 1
    size_ratio = max_area / min_area
    if size_ratio <= 1.5:
        confidence += 0.15  # Panels are very similar in size
    elif size_ratio <= 2.0:
        confidence += 0.05
    elif size_ratio > 3.0:
        confidence -= 0.2   # Massive size difference — likely false positive

    # Aspect ratio check: all panels should be reasonably shaped
    aspect_ratios = [p.aspect_ratio for p in panels]
    min_aspect = min(aspect_ratios)
    if min_aspect >= 0.5:
        confidence += 0.1   # All panels are well-proportioned
    elif min_aspect < 0.3:
        confidence -= 0.15  # Some panel is absurdly narrow/tall

    # Grid regularity score
    rows, cols = grid
    if rows >= 2 and cols >= 2:
        confidence += 0.15  # True 2D grid is strong evidence
    elif rows >= 1 and cols >= 1 and rows <= 4 and cols <= 4:
        confidence += 0.05

    # Panel count bonus
    if n_panels >= 4:
        confidence += 0.1   # 4+ panels is strong evidence
    elif n_panels >= 2:
        confidence += 0.05

    return max(min(confidence, 1.0), 0.0)


def _get_layout(grid: Tuple[int, int]) -> PanelLayout:
    """Map grid dimensions to layout enum."""
    layout_map = {
        (1, 1): PanelLayout.SINGLE,
        (1, 2): PanelLayout.GRID_1x2,
        (1, 3): PanelLayout.GRID_1x3,
        (1, 4): PanelLayout.GRID_1x4,
        (2, 1): PanelLayout.GRID_2x1,
        (2, 2): PanelLayout.GRID_2x2,
        (2, 3): PanelLayout.GRID_2x3,
        (3, 1): PanelLayout.GRID_3x1,
        (3, 2): PanelLayout.GRID_3x2,
        (3, 3): PanelLayout.GRID_3x3,
    }
    return layout_map.get(grid, PanelLayout.IRREGULAR)


def _assign_labels(panels: List[BoundingBox]) -> List[str]:
    """
    Assign panel labels based on position (left-to-right, top-to-bottom).
    Uses A, B, C, D... for ≤26 panels, else panel_0, panel_1, etc.
    """
    sorted_panels = sorted(panels, key=lambda p: (p.y1, p.x1))

    if len(sorted_panels) <= 26:
        return [chr(65 + i) for i in range(len(sorted_panels))]
    else:
        return [f"panel_{i}" for i in range(len(sorted_panels))]


def _assign_grid_positions(
    panels: List[BoundingBox],
    grid: Tuple[int, int]
) -> List[Tuple[int, int]]:
    """
    Assign (row, col) positions to panels based on their spatial location.
    """
    rows, cols = grid
    sorted_panels = sorted(panels, key=lambda p: (p.y1, p.x1))

    positions = []
    for i, panel in enumerate(sorted_panels):
        row = i // cols
        col = i % cols
        positions.append((row, col))

    return positions


# ─── Public API ──────────────────────────────────────────────────────────────

def detect_compound_figure(image_path: str) -> CompoundFigureAnalysis:
    """
    Detect if an image is a compound figure with multiple panels.

    Uses white-space border detection and grid inference to identify
    multi-panel medical figures commonly found in clinical literature.

    Args:
        image_path: Path to the image file

    Returns:
        CompoundFigureAnalysis with detection results

    Raises:
        ValueError: If image cannot be opened
    """
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as e:
        raise ValueError(f"Cannot open image '{image_path}': {e}")

    w, h = image.size
    image_area = w * h

    _single = CompoundFigureAnalysis(
        is_compound=False,
        confidence=0.0,
        num_panels=1,
        panel_positions=[],
        detected_labels=[],
        grid_structure=None,
        layout=PanelLayout.SINGLE,
    )

    # Too small to be compound
    if w < 200 or h < 200:
        return _single

    # Convert to grayscale numpy array
    gray = np.array(image.convert("L"))

    # Find horizontal and vertical separators (internal only)
    h_separators = _find_separators(gray, axis=0)
    v_separators = _find_separators(gray, axis=1)

    # Convert separators to panel regions
    h_regions = _separators_to_splits(h_separators, h)
    v_regions = _separators_to_splits(v_separators, w)

    # Build panel bounding boxes from grid intersections
    panels = []
    for row_idx, (y_start, y_end) in enumerate(h_regions):
        for col_idx, (x_start, x_end) in enumerate(v_regions):
            bbox = BoundingBox(x1=x_start, y1=y_start, x2=x_end, y2=y_end)
            panels.append(bbox)

    # Validate panels (size, area, aspect ratio)
    panels = _validate_panels(panels, image_area)

    # Reject if size consistency is poor (largest >> smallest)
    if not _check_size_consistency(panels):
        return _single

    # Infer grid structure
    grid = _infer_grid(h_regions, v_regions)

    # Compute confidence
    confidence = _compute_confidence(panels, grid, (w, h))

    # Determine if compound
    is_compound = len(panels) >= 2 and confidence >= MIN_COMPOUND_CONFIDENCE

    if not is_compound:
        return CompoundFigureAnalysis(
            is_compound=False,
            confidence=confidence,
            num_panels=1,
            panel_positions=[],
            detected_labels=[],
            grid_structure=None,
            layout=PanelLayout.SINGLE,
        )

    # Assign labels and layout
    labels = _assign_labels(panels)
    layout = _get_layout(grid)

    return CompoundFigureAnalysis(
        is_compound=True,
        confidence=confidence,
        num_panels=len(panels),
        panel_positions=panels,
        detected_labels=labels,
        grid_structure=grid,
        layout=layout,
    )


def split_compound_figure(image_path: str) -> List[SubfigureData]:
    """
    Split a compound figure into individual subfigures.

    First runs detection, then crops each panel from the original image.
    If the image is not compound, returns a single SubfigureData with
    the full image.

    Args:
        image_path: Path to the image file

    Returns:
        List of SubfigureData, one per detected panel
    """
    analysis = detect_compound_figure(image_path)
    image = Image.open(image_path).convert("RGB")

    if not analysis.is_compound:
        w, h = image.size
        return [SubfigureData(
            image=image,
            bbox=BoundingBox(x1=0, y1=0, x2=w, y2=h),
            panel_id="A",
            label=None,
            position=0,
            grid_position=(0, 0),
            confidence=1.0,
        )]

    # Assign grid positions
    grid_positions = _assign_grid_positions(
        analysis.panel_positions,
        analysis.grid_structure
    )

    # Sort panels for consistent ordering (top-to-bottom, left-to-right)
    sorted_data = sorted(
        zip(analysis.panel_positions, analysis.detected_labels, grid_positions),
        key=lambda x: (x[0].y1, x[0].x1)
    )

    subfigures = []
    for i, (bbox, label, grid_pos) in enumerate(sorted_data):
        cropped = image.crop((bbox.x1, bbox.y1, bbox.x2, bbox.y2))

        subfigures.append(SubfigureData(
            image=cropped,
            bbox=bbox,
            panel_id=label,
            label=label,
            position=i,
            grid_position=grid_pos,
            confidence=analysis.confidence,
        ))

    return subfigures


# ─── Utility Functions ───────────────────────────────────────────────────────

def save_subfigures(
    subfigures: List[SubfigureData],
    output_dir: str,
    base_name: str = "panel"
) -> List[str]:
    """
    Save subfigure images to disk.

    Args:
        subfigures: List of detected subfigures
        output_dir: Directory to save images
        base_name: Base filename prefix

    Returns:
        List of saved file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    for sf in subfigures:
        filename = f"{base_name}_{sf.panel_id}.jpg"
        filepath = os.path.join(output_dir, filename)
        sf.image.save(filepath, "JPEG", quality=95)
        paths.append(filepath)
    return paths


def get_analysis_summary(analysis: CompoundFigureAnalysis) -> str:
    """
    Human-readable summary of compound figure analysis.

    Returns:
        Formatted string summary
    """
    if not analysis.is_compound:
        return "Single image (not a compound figure)"

    rows, cols = analysis.grid_structure
    labels = ", ".join(analysis.detected_labels)
    return (
        f"Compound figure detected: {analysis.num_panels} panels "
        f"in {rows}x{cols} grid layout (panels: {labels}), "
        f"confidence: {analysis.confidence:.0%}"
    )


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.subfigure_detector <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    print(f"Analyzing: {image_path}")

    analysis = detect_compound_figure(image_path)
    print(f"\n{get_analysis_summary(analysis)}")

    if analysis.is_compound:
        subfigures = split_compound_figure(image_path)
        print(f"\nExtracted {len(subfigures)} panels:")
        for sf in subfigures:
            print(f"  Panel {sf.panel_id}: {sf.bbox.width}x{sf.bbox.height}px "
                  f"at ({sf.bbox.x1},{sf.bbox.y1}) confidence={sf.confidence:.0%}")

        # Save panels
        out_dir = os.path.join(os.path.dirname(image_path), "panels")
        paths = save_subfigures(subfigures, out_dir)
        print(f"\nPanels saved to: {out_dir}")
        for p in paths:
            print(f"  {p}")
