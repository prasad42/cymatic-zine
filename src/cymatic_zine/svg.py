from __future__ import annotations

from dataclasses import dataclass
from html import escape
import math

import contourpy
import numpy as np


DEFAULT_COLORS = (
    "#3155a6",
    "#2378ad",
    "#15969e",
    "#26a66f",
    "#72b83d",
    "#bad12f",
    "#f2df18",
)


@dataclass(frozen=True)
class RenderSettings:
    colors: tuple[str, ...] = DEFAULT_COLORS
    line_width_in: float = 0.012
    minimum_gap_in: float = 0.025
    background: str = "#f4efe4"
    base_contours: int = 1
    maximum_contours: int = 13
    accelerating_density: bool = True
    hatch_threshold: float = 0.42


def _density_count(panel: int, panel_count: int, settings: RenderSettings) -> int:
    if panel_count == 1:
        return settings.base_contours
    progress = panel / (panel_count - 1)
    if settings.accelerating_density:
        progress = progress**1.45
    return round(settings.base_contours + progress * (settings.maximum_contours - settings.base_contours))


def _path(points: np.ndarray, y_offset: float = 0.0) -> str:
    if len(points) < 2:
        return ""
    coordinates = [f"{points[0, 0] * 700:.2f},{(points[0, 1] - y_offset) * 700:.2f}"]
    coordinates.extend(f"{x * 700:.2f},{(y - y_offset) * 700:.2f}" for x, y in points[1:])
    return "M " + " L ".join(coordinates)


def _split_by_visibility(
    points: np.ndarray,
    level_rank: int,
    panel_count: int,
    settings: RenderSettings,
    crop: tuple[int, int],
) -> list[np.ndarray]:
    output: list[np.ndarray] = []
    current: list[np.ndarray] = []
    for point in points:
        panel = int(np.clip(math.floor(point[1]), 0, panel_count - 1))
        visible = crop[0] <= panel < crop[1] and level_rank < _density_count(
            panel, panel_count, settings
        )
        if visible:
            current.append(point)
        elif len(current) >= 2:
            output.append(np.asarray(current))
            current = []
        else:
            current = []
    if len(current) >= 2:
        output.append(np.asarray(current))
    return output


def _gradient_stops(colors: tuple[str, ...], panel_count: int, crop: tuple[int, int]) -> str:
    relevant = colors[:panel_count]
    if len(relevant) == 1:
        return f'<stop offset="0%" stop-color="{escape(relevant[0])}"/><stop offset="100%" stop-color="{escape(relevant[0])}"/>'
    stops = []
    crop_span = crop[1] - crop[0]
    for index in range(crop[0], crop[1]):
        local = ((index + 0.5) - crop[0]) / crop_span
        stops.append(f'<stop offset="{local * 100:.2f}%" stop-color="{escape(relevant[index])}"/>')
    return "".join(stops)


def _wood_hatches(
    field: np.ndarray,
    panel_count: int,
    settings: RenderSettings,
    crop: tuple[int, int],
) -> list[str]:
    panel_height = field.shape[0] / panel_count
    paths: list[str] = []
    for panel in range(crop[0], crop[1]):
        # Higher panels are sparse; later panels receive progressively tighter hatching.
        spacing_in = max(settings.minimum_gap_in, 0.18 - 0.12 * panel / max(panel_count - 1, 1))
        step = max(1, round(spacing_in * panel_height / 7.0))
        start = round(panel * panel_height)
        stop = round((panel + 1) * panel_height)
        for row in range(start, stop, step):
            mask = np.abs(field[row]) >= settings.hatch_threshold
            changes = np.diff(np.pad(mask.astype(np.int8), (1, 1)))
            starts = np.flatnonzero(changes == 1)
            ends = np.flatnonzero(changes == -1)
            y = (row / panel_height - crop[0]) * 700
            for left, right in zip(starts, ends, strict=True):
                if right - left < 2:
                    continue
                x1 = left / (field.shape[1] - 1) * 700
                x2 = (right - 1) / (field.shape[1] - 1) * 700
                paths.append(f'<path d="M {x1:.2f},{y:.2f} L {x2:.2f},{y:.2f}"/>')
    return paths


def _zero_crossings(values: np.ndarray) -> np.ndarray:
    crossings: list[float] = []
    for index in range(len(values) - 1):
        left = float(values[index])
        right = float(values[index + 1])
        if left == 0.0:
            crossings.append(float(index))
        elif left * right < 0.0:
            crossings.append(index + left / (left - right))
    return np.asarray(crossings)


def _fold_connectors(
    field: np.ndarray,
    panel_count: int,
    crop: tuple[int, int],
) -> list[str]:
    """Bridge nodal contours through folds where local plate fields meet."""
    panel_height = field.shape[0] / panel_count
    connectors: list[str] = []
    for panel in range(max(1, crop[0]), min(panel_count, crop[1])):
        seam = round(panel * panel_height)
        radius = max(2, round(panel_height * 0.018))
        upper = _zero_crossings(np.mean(field[seam - radius : seam], axis=0))
        lower = _zero_crossings(np.mean(field[seam : seam + radius], axis=0))
        if not len(upper) or not len(lower):
            continue
        count = min(len(upper), len(lower))
        upper = upper[np.linspace(0, len(upper) - 1, count).round().astype(int)]
        lower = lower[np.linspace(0, len(lower) - 1, count).round().astype(int)]
        for start, end in zip(upper, lower, strict=True):
            start_x = start / (field.shape[1] - 1) * 700
            end_x = end / (field.shape[1] - 1) * 700
            if not (18.0 < start_x < 682.0 and 18.0 < end_x < 682.0):
                continue
            local_seam = (seam / panel_height - crop[0]) * 700
            reach = max(8.0, panel_height * 0.025)
            connectors.append(
                f'<path d="M {start_x:.2f},{local_seam - reach:.2f} '
                f'C {start_x:.2f},{local_seam - 2.0:.2f} '
                f'{end_x:.2f},{local_seam + 2.0:.2f} '
                f'{end_x:.2f},{local_seam + reach:.2f}"/>'
            )
    return connectors


def render_svg(
    x: np.ndarray,
    y: np.ndarray,
    field: np.ndarray,
    settings: RenderSettings = RenderSettings(),
    *,
    medium: str = "paper",
    crop: tuple[int, int] | None = None,
) -> str:
    panel_count = round(float(y[-1]) + 0.5)
    crop = crop or (0, panel_count)
    if not (0 <= crop[0] < crop[1] <= panel_count):
        raise ValueError("Invalid panel crop")
    if len(settings.colors) < panel_count:
        raise ValueError("Provide at least one color for every panel")

    levels = np.linspace(-0.88, 0.88, settings.maximum_contours)
    ranked = sorted(range(len(levels)), key=lambda index: abs(levels[index]))
    rank_by_index = {level_index: rank for rank, level_index in enumerate(ranked)}
    generator = contourpy.contour_generator(x=x, y=y, z=field, name="serial")
    contour_paths: list[str] = []
    for level_index, level in enumerate(levels):
        for line in generator.lines(float(level)):
            for section in _split_by_visibility(
                line, rank_by_index[level_index], panel_count, settings, crop
            ):
                path_data = _path(section, crop[0])
                if path_data:
                    contour_paths.append(f'<path d="{path_data}"/>')
    contour_paths.extend(_fold_connectors(field, panel_count, crop))

    width = 700
    height = 700 * (crop[1] - crop[0])
    stroke_width = settings.line_width_in * 100
    common = 'fill="none" stroke-linecap="round" stroke-linejoin="round"'
    if medium == "paper":
        stops = _gradient_stops(settings.colors, panel_count, crop)
        artwork = (
            f'<rect width="100%" height="100%" fill="{escape(settings.background)}"/>'
            f'<defs><linearGradient id="hope" x1="0" y1="0" x2="0" y2="1">{stops}</linearGradient></defs>'
            f'<g {common} stroke="url(#hope)" opacity="0.24" stroke-width="{stroke_width * 2.8:.2f}">'
            + "".join(contour_paths)
            + f'</g><g {common} stroke="url(#hope)" stroke-width="{stroke_width:.2f}">'
            + "".join(contour_paths)
            + "</g>"
        )
    elif medium == "wood":
        hatches = _wood_hatches(field, panel_count, settings, crop)
        artwork = (
            f'<g {common} stroke="#000" stroke-width="{stroke_width:.2f}">' + "".join(contour_paths) + "</g>"
            f'<g {common} stroke="#000" stroke-width="{stroke_width * 0.75:.2f}" opacity="0.72">'
            + "".join(hatches)
            + "</g>"
        )
    else:
        raise ValueError("medium must be 'paper' or 'wood'")

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="7in" height="{7 * (crop[1] - crop[0])}in" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Cumulative cymatic voice field">'
        f'<title>Cumulative cymatic voice field, panels {crop[0] + 1} through {crop[1]}</title>'
        + artwork
        + "</svg>"
    )
