"""
Classes for displaying rich error messages.

Usage:
```python
from pathlib import Path
from .reporting import Error, Pointer, Span, SrcFile, ColorTheme

srcfile = SrcFile(
    path=Path("path/to/file.dewy"),
    body="printl'Hello, World'",
)

error = Error(
    srcfile=srcfile,
    title="dewy.errors.E1234",
    message="Unable to juxtapose identifier and string",
    pointer_messages=[
        Pointer(
            span=Span(6, 6),
            message="tried to juxtapose printl (string:>void) and 'Hello, World' (string)\nexpected whitespace or operator between identifier and string",
        ),
    ],
    hint="insert a space or an operator",
)

print(error)
```

For discussion on what to include in error messages, see: https://langdev.stackexchange.com/questions/1790/what-should-be-included-in-error-messages

TODO features:
[x] severity levels (error, warning, info, hint)
[ ] linking to error code documentation website
[ ] terminal link to location of error in source code
[ ] structured output mode (probably json)
[ ] stack traces (perhaps higher order messages consisting of a list of errors?)
[x] spans overlapping multiple lines
[ ] displaying multiple surrounding lines for extra context. TBD how much to display.
[ ] source code syntax highlighting (very long term goal)
[.] for unknown identifiers, look up possible similar identifiers for help message (handled by higher level process)
"""
from __future__ import annotations  # so older python versions (>=3.10) can use this module
from dataclasses import dataclass, field
from pathlib import Path
from bisect import bisect_right
from os import PathLike
from typing import Literal, NoReturn, TypeAlias
import re

Severity: TypeAlias = Literal["error", "warning", "info", "hint"]

ColorName: TypeAlias = Literal["cyan", "green", "yellow", "blue", "purple", "pink", "light_orange", "red", "white"]

RESET = "\033[0m"
FG_RED = "\033[31m"
FG_YELLOW = "\033[33m"
FG_BLUE = "\033[34m"
FG_CYAN = "\033[36m"
FG_DIM_GRAY = "\033[90m"
FG_LIGHT_GRAY = "\033[38;5;245m"
FG_WHITE_ON_RED = "\033[1;97;41m"
POINTER_COLOR_CODES = (
    # "\033[95m",      # Magenta (washed out compared to purple)
    "\033[96m",      # Cyan
    # "\033[90m",      # Gray   (too dark)
    # "\033[91m",      # Red    (too red)
    "\033[92m",      # Green
    "\033[93m",      # Yellow
    "\033[94m",      # Blue
    # "\033[38;5;208m",  # Orange (too similar when next to pink)
    "\033[38;5;135m",  # Purple
    # "\033[38;5;141m",  # Light Purple (too similar to purple/magenta)
    "\033[38;5;211m",  # Pink
    "\033[38;5;214m",  # Light Orange
    # "\033[38;5;246m",  # Medium-light gray
    # "\033[38;5;248m",  # Light gray
    # "\033[38;5;250m",  # Very light gray

)

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")

COLOR_NAME_TO_CODE: dict[ColorName, str] = {
    "cyan": "\033[96m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "purple": "\033[38;5;135m",
    "pink": "\033[38;5;211m",
    "light_orange": "\033[38;5;214m",
    "red": "\033[91m",
    "white": "\033[97m",
}


class ColorTheme:
    def __init__(self, enabled:bool=True) -> None:
        self.enabled = enabled
    
    def _wrap(self, text:str, code:str|None) -> str:
        if not self.enabled or not code:
            return text
        return f"{code}{text}{RESET}"
    
    def title(self, text:str, severity:Severity) -> str:
        if severity == "error":
            color = FG_RED
        elif severity == "warning":
            color = FG_YELLOW
        elif severity == "info":
            color = FG_BLUE
        elif severity == "hint":
            color = FG_CYAN
        return self._wrap(text, color)
    
    def marker(self, text:str, severity:Severity) -> str:
        if severity == "error":
            color = FG_RED
        elif severity == "warning":
            color = FG_YELLOW
        elif severity == "info":
            color = FG_BLUE
        elif severity == "hint":
            color = FG_CYAN
        return self._wrap(text, color)
    
    def line_number(self, text:str) -> str:
        return self._wrap(text, FG_LIGHT_GRAY)
    
    def help_label(self, text:str) -> str:
        return self._wrap(text, FG_LIGHT_GRAY)

    def color_char(self, char:str, color_code:str|None) -> str:
        return self._wrap(char, color_code)
    
    @property
    def pointer_palette(self) -> tuple[str|None, ...]:
        if not self.enabled:
            return (None,)
        return POINTER_COLOR_CODES


PointerPlacement = Literal["above", "below"]


@dataclass
class Span:
    """
    python range rules, i.e. [start,stop), indices are in between items, not the indices of actual items. 
    0-width implies pointing between characters
    """
    start:int
    stop:int
    
    @property
    def is_zero_width(self) -> bool:
        return self.start == self.stop
    
    def clamp_to(self, lo:int, hi:int) -> Span:
        start = min(max(self.start, lo), hi)
        stop = min(max(self.stop, lo), hi)
        return Span(start, stop)


@dataclass
class Pointer:
    span:Span|list[Span]
    message:str
    placement:PointerPlacement|None = None
    color:int|ColorName|None = None

    def __post_init__(self) -> None:
        if isinstance(self.span, Span):
            self.span = [self.span]


@dataclass
class SrcFile:
    path:PathLike[str]|None
    body:str
    _line_starts:list[int] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        if self.path is not None and not isinstance(self.path, Path):
            self.path = Path(self.path)
        if not self._line_starts:
            self._line_starts = self._compute_line_starts(self.body)
    
    @staticmethod
    def _compute_line_starts(text:str) -> list[int]:
        starts = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                starts.append(i + 1)
        return starts
    
    @classmethod
    def from_text(cls, body:str, path:PathLike[str]|None=None) -> SrcFile:
        return cls(path=path, body=body)

    def offset_to_row_col(self, index:int) -> tuple[int, int]:
        index = max(0, min(index, len(self.body)))
        line_idx = bisect_right(self._line_starts, index) - 1
        line_start = self._line_starts[line_idx]
        return (line_idx, index - line_start)
    
    def line_bounds(self, row:int) -> tuple[int, int]:
        start = self._line_starts[row]
        if row + 1 < len(self._line_starts):
            end = self._line_starts[row + 1] - 1
        else:
            end = len(self.body)
        return start, end
    
    def line_text(self, row:int) -> str:
        start, end = self.line_bounds(row)
        return self.body[start:end]


@dataclass
class _Segment:
    pointer:Pointer
    line_idx:int
    start_col:int
    end_col:int
    anchor_col:int
    placement:PointerPlacement|None
    color_code:str|None
    color_id:int|None = None
    auto_assigned:bool = False
    render_pointer:bool = True
    show_message:bool = True
    show_anchor:bool = True
    
    @property
    def is_zero_width(self) -> bool:
        return self.start_col == self.end_col


@dataclass
class Report:
    srcfile:SrcFile
    severity:Severity
    title:str|None=None
    message:str|None=None
    pointer_messages:Pointer|list[Pointer]=field(default_factory=list)
    hint:str|None=None
    use_color:bool=True
    
    def __post_init__(self) -> None:
        if isinstance(self.pointer_messages, Pointer):
            self.pointer_messages = [self.pointer_messages]

    def __str__(self) -> str:
        sf = self.srcfile
        theme = ColorTheme(self.use_color)
        loc = "input" if sf.path is None else str(sf.path)
        first_index = min(
            (span.start for pm in self.pointer_messages for span in pm.span),
            default=0,
        )
        row_idx, col_idx = sf.offset_to_row_col(first_index)
        
        segments = self._prepare_segments(theme.pointer_palette)
        lines_with_segments = sorted({seg.line_idx for seg in segments})
        if not lines_with_segments:
            line_order = [row_idx]
        else:
            min_line = min(lines_with_segments)
            max_line = max(lines_with_segments)
            line_order = list(range(min_line, max_line + 1))
        max_line_no = max(line_order) + 1
        line_no_width = len(str(max_line_no))
        gutter_pad = " " * max(0, line_no_width - 1)
        
        body_indent = "  "
        block_indent = "    "
        
        out:list[str] = []
        if self.title:
            out.append(f"{self.severity.title()}: {theme.title(self.title, self.severity)}")
            out.append("")
        if self.message:
            marker = "×" if self.severity == "error" else "•"
            out.append(f"{body_indent}{theme.marker(marker, self.severity)} {self.message}")
        out.append(f"{block_indent}{gutter_pad}╭─[{loc}:{row_idx+1}:{col_idx+1}]")
        
        segments_by_line:dict[int, list[_Segment]] = {}
        for seg in segments:
            segments_by_line.setdefault(seg.line_idx, []).append(seg)
        
        for line_idx in line_order:
            per_line = segments_by_line.get(line_idx, [])
            out.extend(self._render_line(line_idx, per_line, block_indent, line_no_width, theme))
        
        out.append(f"{block_indent}{gutter_pad}╰───")
        if self.hint:
            label_text = "help:"
            label = theme.help_label(label_text)
            first, *rest = self.hint.splitlines() or [""]
            out.append(f"{body_indent}{label} {first}")
            if rest:
                continuation = " " * (len(body_indent) + len(label_text) + 1)
                for chunk in rest:
                    out.append(f"{continuation}{chunk}")
        return "\n".join(out)
    
    @staticmethod
    def _find_adjacent_segments(segments:list[_Segment]) -> dict[int, set[int]]:
        """
        Build adjacency graph for segments.
        Two segments are adjacent if they are on the same line, have the same placement,
        and their spans touch (left.end_col == right.start_col, or for zero-width,
        start_col values are consecutive).
        Returns a dict mapping segment id to set of adjacent segment ids.
        """
        adjacency:dict[int, set[int]] = {}
        for seg in segments:
            adjacency[id(seg)] = set()
        
        by_line_placement:dict[tuple[int, PointerPlacement|None], list[_Segment]] = {}
        for seg in segments:
            key = (seg.line_idx, seg.placement)
            by_line_placement.setdefault(key, []).append(seg)
        
        for segs in by_line_placement.values():
            segs.sort(key=lambda s: (s.start_col, s.end_col))
            for i, left in enumerate(segs):
                for right in segs[i+1:]:
                    adjacent = False
                    if left.is_zero_width and right.is_zero_width:
                        if abs(left.start_col - right.start_col) <= 1:
                            adjacent = True
                    elif not left.is_zero_width and not right.is_zero_width:
                        if left.end_col == right.start_col:
                            adjacent = True
                    elif left.is_zero_width:
                        if left.start_col == right.start_col or left.start_col == right.start_col - 1:
                            adjacent = True
                    else:
                        if right.start_col == left.end_col or right.start_col == left.end_col - 1:
                            adjacent = True
                    
                    if adjacent:
                        left_id = id(left)
                        right_id = id(right)
                        adjacency[left_id].add(right_id)
                        adjacency[right_id].add(left_id)
                    elif not left.is_zero_width and not right.is_zero_width:
                        if left.end_col < right.start_col:
                            break
        
        return adjacency
    
    def _assign_colors_to_segments(
        self,
        segments:list[_Segment],
        palette:tuple[str|None, ...],
        adjacency:dict[int, set[int]],
    ) -> None:
        """
        Assign colors to segments based on color_id grouping and adjacency constraints.
        - Segments with the same color_id always get the same color
        - Adjacent segments with different color_ids must have different colors
        - If there are fewer or equal color_ids than colors, assign sequentially
        - Otherwise, use all colors while respecting adjacency constraints
        - Segments with pre-assigned color_code (from color names) are skipped
        """
        palette_len = len(palette)
        
        id_to_seg:dict[int, _Segment] = {}
        for seg in segments:
            id_to_seg[id(seg)] = seg
        
        segments_needing_assignment = [seg for seg in segments if seg.color_code is None]
        
        color_id_to_segments:dict[int|None, list[_Segment]] = {}
        for seg in segments_needing_assignment:
            color_id_to_segments.setdefault(seg.color_id, []).append(seg)
        
        num_color_ids = len(color_id_to_segments)
        
        color_id_to_color:dict[int|None, str|None] = {}
        segment_id_to_color:dict[int, str|None] = {}
        
        if num_color_ids <= palette_len:
            color_index = 0
            for color_id in sorted(color_id_to_segments.keys(), key=lambda x: x if x is not None else float('inf')):
                color = palette[color_index % palette_len]
                color_id_to_color[color_id] = color
                for seg in color_id_to_segments[color_id]:
                    seg_id = id(seg)
                    segment_id_to_color[seg_id] = color
                    seg.color_code = color
                color_index += 1
        else:
            def get_adjacent_colors(seg_id:int, exclude_color_id:int|None) -> set[str|None]:
                """Get colors used by adjacent segments with different color_ids."""
                colors = set()
                for adj_seg_id in adjacency.get(seg_id, set()):
                    adj_seg = id_to_seg[adj_seg_id]
                    if adj_seg.color_id != exclude_color_id:
                        if adj_seg_id in segment_id_to_color:
                            colors.add(segment_id_to_color[adj_seg_id])
                        elif adj_seg.color_code is not None:
                            colors.add(adj_seg.color_code)
                return colors
            
            def find_available_color(color_id:int|None, segments_in_group:list[_Segment]) -> str|None:
                """Find a color for a color_id group that doesn't conflict with adjacent segments.
                Tries to use all colors by preferring less-used colors."""
                if color_id in color_id_to_color:
                    candidate_color = color_id_to_color[color_id]
                    adjacent_colors = set()
                    for seg in segments_in_group:
                        adjacent_colors.update(get_adjacent_colors(id(seg), color_id))
                    if candidate_color not in adjacent_colors:
                        return candidate_color
                
                color_usage:dict[str|None, int] = {}
                for used_color in color_id_to_color.values():
                    color_usage[used_color] = color_usage.get(used_color, 0) + 1
                
                available_colors:list[tuple[str|None, int]] = []
                for color in palette:
                    adjacent_colors = set()
                    for seg in segments_in_group:
                        adjacent_colors.update(get_adjacent_colors(id(seg), color_id))
                    if color not in adjacent_colors:
                        usage_count = color_usage.get(color, 0)
                        available_colors.append((color, usage_count))
                
                if available_colors:
                    available_colors.sort(key=lambda x: x[1])
                    return available_colors[0][0]
                
                return palette[0] if palette else None
            
            for color_id, segs_in_group in color_id_to_segments.items():
                color = find_available_color(color_id, segs_in_group)
                color_id_to_color[color_id] = color
                for seg in segs_in_group:
                    seg_id = id(seg)
                    segment_id_to_color[seg_id] = color
                    seg.color_code = color
        
        def get_conflicting_segment(seg_id:int) -> int|None:
            """Find an adjacent segment that has the same color and different color_id."""
            seg = id_to_seg[seg_id]
            seg_color = segment_id_to_color.get(seg_id) or seg.color_code
            for adj_seg_id in adjacency.get(seg_id, set()):
                adj_seg = id_to_seg[adj_seg_id]
                adj_seg_color = segment_id_to_color.get(adj_seg_id) or adj_seg.color_code
                if adj_seg.color_id != seg.color_id and adj_seg_color == seg_color:
                    return adj_seg_id
            return None
        
        def find_color_for_segment(seg_id:int, exclude_colors:set[str|None]) -> str|None:
            """Find a color for a single segment that avoids excluded colors.
            Returns None if no non-excluded color is available."""
            color_usage:dict[str|None, int] = {}
            for used_color in segment_id_to_color.values():
                color_usage[used_color] = color_usage.get(used_color, 0) + 1
            
            available_colors:list[tuple[str|None, int]] = []
            for color in palette:
                if color not in exclude_colors:
                    usage_count = color_usage.get(color, 0)
                    available_colors.append((color, usage_count))
            
            if available_colors:
                available_colors.sort(key=lambda x: x[1])
                return available_colors[0][0]
            
            return None
        
        changed = True
        max_iterations = len(segments_needing_assignment) * 2
        iteration = 0
        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            for seg in segments_needing_assignment:
                seg_id = id(seg)
                conflicting_id = get_conflicting_segment(seg_id)
                if conflicting_id is not None:
                    conflicting_seg = id_to_seg[conflicting_id]
                    seg_color = segment_id_to_color.get(seg_id) or seg.color_code
                    conflicting_color = segment_id_to_color.get(conflicting_id) or conflicting_seg.color_code
                    
                    adjacent_colors = get_adjacent_colors(seg_id, seg.color_id)
                    if conflicting_color is not None:
                        adjacent_colors.add(conflicting_color)
                    
                    new_color = find_color_for_segment(seg_id, adjacent_colors)
                    if new_color is not None and new_color != seg_color:
                        segment_id_to_color[seg_id] = new_color
                        seg.color_code = new_color
                        changed = True
                    elif new_color is None:
                        for color in palette:
                            if color not in adjacent_colors:
                                segment_id_to_color[seg_id] = color
                                seg.color_code = color
                                changed = True
                                break
    
    def _prepare_segments(self, palette:tuple[str|None, ...]) -> list[_Segment]:
        sf = self.srcfile
        segments:list[_Segment] = []
        
        used_color_ids:set[int] = set()
        for pointer in self.pointer_messages:
            if isinstance(pointer.color, int):
                used_color_ids.add(pointer.color)
        
        next_auto_color_id = 0
        while next_auto_color_id in used_color_ids:
            next_auto_color_id += 1
        
        for pointer in self.pointer_messages:
            if isinstance(pointer.color, str):
                color_code = COLOR_NAME_TO_CODE[pointer.color]
                segments.extend(self._build_segments_for_pointer(sf, pointer, color_code, None))
            elif pointer.color is None:
                assigned_color_id = next_auto_color_id
                next_auto_color_id += 1
                while next_auto_color_id in used_color_ids:
                    next_auto_color_id += 1
                segments.extend(self._build_segments_for_pointer(sf, pointer, None, assigned_color_id))
            else:
                assigned_color_id = pointer.color
                segments.extend(self._build_segments_for_pointer(sf, pointer, None, assigned_color_id))
        
        line_to_segments:dict[int, list[_Segment]] = {}
        for seg in segments:
            line_to_segments.setdefault(seg.line_idx, []).append(seg)
        self._assign_default_placements(line_to_segments)
        
        by_line:dict[int, list[_Segment]] = {}
        for seg in segments:
            siblings = by_line.setdefault(seg.line_idx, [])
            siblings.append(seg)
        for line_idx, siblings in by_line.items():
            non_zero = [s for s in siblings if s.render_pointer and not s.is_zero_width]
            non_zero.sort(key=lambda s: s.start_col)
            for left, right in zip(non_zero, non_zero[1:]):
                if left.end_col > right.start_col:
                    raise ValueError(f"overlapping spans on line {line_idx+1}")
        
        adjacency = self._find_adjacent_segments(segments)
        self._assign_colors_to_segments(segments, palette, adjacency)
        
        return segments
    
    def _build_segments_for_pointer(self, sf:SrcFile, pointer:Pointer, color_code:str|None, color_id:int|None=None) -> list[_Segment]:
        segments:list[_Segment] = []
        all_spans = sorted(pointer.span, key=lambda s: (s.start, s.stop))
        line_infos:list[dict[str, int]] = []
        for span in all_spans:
            start_row, _ = sf.offset_to_row_col(span.start)
            if span.is_zero_width:
                end_row, _ = sf.offset_to_row_col(span.stop)
            else:
                end_row, _ = sf.offset_to_row_col(span.stop - 1)
            for line_idx in range(start_row, end_row + 1):
                line_start, line_end = sf.line_bounds(line_idx)
                line_len = line_end - line_start
                if line_idx == start_row:
                    start_col = max(0, min(span.start - line_start, line_len))
                else:
                    start_col = 0
                if span.is_zero_width:
                    end_col = start_col
                elif line_idx == end_row:
                    end_col = max(0, min(span.stop - line_start, line_len))
                else:
                    end_col = line_len
                if start_col > end_col:
                    start_col, end_col = end_col, start_col
                line_infos.append({
                    "line_idx": line_idx,
                    "start_col": start_col,
                    "end_col": end_col,
                    "line_len": line_len,
                })
        
        if len(line_infos) == 1:
            info = line_infos[0]
            start_col = info["start_col"]
            end_col = info["end_col"]
            if start_col == end_col:
                if start_col > 0:
                    start_col -= 1
                    end_col = start_col
                anchor_col = start_col
            else:
                anchor_col = start_col + ((end_col - start_col) - 1) // 2
            segments.append(_Segment(
                pointer=pointer,
                line_idx=info["line_idx"],
                start_col=start_col,
                end_col=end_col,
                anchor_col=anchor_col,
                placement=pointer.placement,
                color_code=color_code,
                color_id=color_id,
            ))
            return segments
        
        message_idx = len(line_infos) - 1
        for idx in range(len(line_infos) - 1, -1, -1):
            info = line_infos[idx]
            if info["end_col"] > info["start_col"]:
                message_idx = idx
                break
        for idx, info in enumerate(line_infos):
            start_col = info["start_col"]
            end_col = info["end_col"]
            is_message_line = idx == message_idx
            if is_message_line and start_col == end_col and start_col > 0:
                start_col -= 1
                end_col = start_col
            if is_message_line and start_col != end_col:
                anchor_col = start_col + ((end_col - start_col) - 1) // 2
            else:
                anchor_col = start_col
            render_pointer = True
            show_anchor = is_message_line
            if not is_message_line and start_col == end_col:
                render_pointer = False
                show_anchor = False
            if pointer.placement is not None:
                segment_placement = pointer.placement
            elif is_message_line:
                segment_placement = None
            else:
                segment_placement = "below"
            segments.append(_Segment(
                pointer=pointer,
                line_idx=info["line_idx"],
                start_col=start_col,
                end_col=end_col,
                anchor_col=anchor_col,
                placement=segment_placement,
                color_code=color_code,
                color_id=color_id,
                show_message=is_message_line,
                show_anchor=show_anchor,
                render_pointer=render_pointer,
            ))
        return segments
    
    def _assign_default_placements(self, line_to_segments:dict[int, list[_Segment]]) -> None:
        for line_idx in sorted(line_to_segments):
            segments = line_to_segments[line_idx]
            non_zero_anchors = {seg.anchor_col for seg in segments if not seg.is_zero_width and seg.show_anchor}
            for seg in segments:
                if seg.placement is not None:
                    continue
                if seg.is_zero_width:
                    slash_cols = {seg.start_col, seg.start_col + 1}
                    overlaps_anchor = any(col in non_zero_anchors for col in slash_cols)
                    if overlaps_anchor:
                        seg.placement = "above"
                    else:
                        seg.placement = "below"
                else:
                    seg.placement = "below"
                seg.auto_assigned = True
        self._apply_adjacent_pair_rules(line_to_segments)

    def _apply_adjacent_pair_rules(self, line_to_segments:dict[int, list[_Segment]]) -> None:
        simple_lines:list[int] = []
        for line_idx in sorted(line_to_segments):
            segments = line_to_segments[line_idx]
            if not segments:
                continue
            if not all(seg.auto_assigned for seg in segments):
                continue
            if any(seg.placement != "below" for seg in segments):
                continue
            simple_lines.append(line_idx)

        i = 0
        while i < len(simple_lines) - 1:
            first_line = simple_lines[i]
            second_line = simple_lines[i + 1]
            if second_line == first_line + 1:
                for seg in line_to_segments[first_line]:
                    if seg.auto_assigned:
                        seg.placement = "above"
                for seg in line_to_segments[second_line]:
                    if seg.auto_assigned:
                        seg.placement = "below"
                i += 2
            else:
                i += 1
    
    def _render_line(
        self,
        line_idx:int,
        segments:list[_Segment],
        block_indent:str,
        line_no_width:int,
        theme:ColorTheme,
    ) -> list[str]:
        sf = self.srcfile
        line_no = line_idx + 1
        line_text = sf.line_text(line_idx)
        line_display = self._line_display(line_text, segments, theme)
        
        line_no_text = theme.line_number(f"{line_no:>{line_no_width}}")
        line_prefix = f"  {line_no_text} | "
        pointer_prefix = "  " + " " * (line_no_width + 1) + "· "
        
        above = [seg for seg in segments if seg.render_pointer and seg.placement == "above"]
        below = [seg for seg in segments if seg.render_pointer and seg.placement == "below"]
        
        width = max(
            len(line_display),
            self._segments_width(above),
            self._segments_width(below),
        )
        
        output:list[str] = []
        output.extend(self._render_pointer_layer(above, pointer_prefix, width, "above", theme))
        output.append(f"{line_prefix}{line_display}")
        output.extend(self._render_pointer_layer(below, pointer_prefix, width, "below", theme))
        return output
    
    @staticmethod
    def _visible_length(text:str) -> int:
        return len(ANSI_ESCAPE_RE.sub("", text))
    
    def _visualize_control_chars(self, line_text:str, theme:ColorTheme) -> str:
        """Convert control characters like \f, \v, \r, \0, etc. to their visual representations ␌, ␋, ␍, ␀, etc."""
        out:list[str] = []
        for ch in line_text:
            code = ord(ch)
            if (code < 0x20 and ch not in ("\t", "\n")) or code == 0x7F:
                if code == 0x7F:
                    glyph = "\u2421"  # ␡
                else:
                    glyph = chr(0x2400 + code)
                out.append(theme._wrap(glyph, FG_WHITE_ON_RED))
            else:
                out.append(ch)
        return "".join(out)
    
    def _line_display(self, line_text:str, segments:list[_Segment], theme:ColorTheme) -> str:
        marker = self._blank_line_marker(line_text, segments, theme)
        if marker is not None:
            return marker
        return self._visualize_control_chars(line_text, theme)
    
    @staticmethod
    def _blank_line_marker(line_text:str, segments:list[_Segment], theme:ColorTheme) -> str|None:
        if line_text.strip():
            return None
        dots = [
            theme.color_char("|", seg.color_code)
            for seg in segments
            if not seg.render_pointer and not seg.show_message
        ]
        if not dots:
            return None
        return " ".join(dots)
    
    def _render_pointer_layer(
        self,
        segments:list[_Segment],
        pointer_prefix:str,
        width:int,
        placement:PointerPlacement,
        theme:ColorTheme,
    ) -> list[str]:
        render_segments = [seg for seg in segments if seg.render_pointer]
        if not render_segments:
            return []
        baseline, effective_width = self._build_baseline(render_segments, max(width, 0), placement, theme)
        messages = self._build_message_lines(render_segments, effective_width, placement, theme)
        prefixed:list[str] = []
        if placement == "above":
            prefixed.extend(f"{pointer_prefix}{line}" for line in messages)
            prefixed.append(f"{pointer_prefix}{baseline}")
        else:
            prefixed.append(f"{pointer_prefix}{baseline}")
            prefixed.extend(f"{pointer_prefix}{line}" for line in messages)
        return prefixed
    
    def _build_baseline(
        self,
        segments:list[_Segment],
        width:int,
        placement:PointerPlacement,
        theme:ColorTheme,
    ) -> tuple[str, int]:
        chars:list[str] = [" "] * width
        
        def ensure(idx:int) -> None:
            if idx >= len(chars):
                chars.extend([" "] * (idx - len(chars) + 1))
        
        for seg in segments:
            if seg.is_zero_width:
                continue
            for idx in range(seg.start_col, seg.end_col):
                ensure(idx)
                chars[idx] = theme.color_char("─", seg.color_code)
        for seg in segments:
            if seg.is_zero_width or not seg.show_anchor:
                continue
            ensure(seg.anchor_col)
            marker = "┬" if placement == "below" else "┴"
            chars[seg.anchor_col] = theme.color_char(marker, seg.color_code)
        
        zero_segments = sorted((seg for seg in segments if seg.is_zero_width), key=lambda s: s.start_col)
        i = 0
        while i < len(zero_segments):
            run_start = zero_segments[i].start_col
            run_count = 1
            j = i + 1
            prev_col = run_start
            while j < len(zero_segments):
                col = zero_segments[j].start_col
                if col <= prev_col + 1:
                    run_count += 1
                    prev_col = col
                    j += 1
                else:
                    break
            run_segments = zero_segments[i:j]
            pattern = self._zero_pattern(run_segments, placement, theme)
            for offset, ch in enumerate(pattern):
                idx = run_start + offset
                ensure(idx)
                chars[idx] = ch
            i = j
        
        baseline = "".join(chars).rstrip()
        return baseline, len(chars)
    
    def _build_message_lines(
        self,
        segments:list[_Segment],
        width:int,
        placement:PointerPlacement,
        theme:ColorTheme,
    ) -> list[str]:
        message_segments = [seg for seg in segments if seg.show_message]
        if not message_segments:
            return []
        lines:list[str] = []
        if placement == "below":
            order = sorted(message_segments, key=lambda s: s.anchor_col, reverse=True)
            pending = [(seg.anchor_col, seg.color_code) for seg in order]
            for seg in order:
                line_chars = [" "] * width
                for anchor, color in pending:
                    if anchor == seg.anchor_col:
                        continue
                    if anchor >= len(line_chars):
                        line_chars.extend([" "] * (anchor - len(line_chars) + 1))
                    if line_chars[anchor] == " ":
                        line_chars[anchor] = theme.color_char("│", color)
                anchor = seg.anchor_col
                if anchor >= len(line_chars):
                    line_chars.extend([" "] * (anchor - len(line_chars) + 1))
                line_chars[anchor] = theme.color_char("╰", seg.color_code)
                base = "".join(line_chars).rstrip()
                text_lines = seg.pointer.message.splitlines() or [""]
                first, *rest = text_lines
                colored_section = theme.color_char(f"─ {first}", seg.color_code)
                lines.append(f"{base}{colored_section}")
                if rest:
                    continuation = " " * (anchor + 3)
                    for chunk in rest:
                        lines.append(theme.color_char(f"{continuation}{chunk}", seg.color_code))
                pending = [(a, c) for (a, c) in pending if a != anchor]
        else:
            order = sorted(message_segments, key=lambda s: s.anchor_col)
            active:list[tuple[int, str|None]] = []
            for seg in order:
                line_chars = [" "] * width
                for anchor, color in active:
                    if anchor >= len(line_chars):
                        line_chars.extend([" "] * (anchor - len(line_chars) + 1))
                    if line_chars[anchor] == " ":
                        line_chars[anchor] = theme.color_char("│", color)
                anchor = seg.anchor_col
                if anchor >= len(line_chars):
                    line_chars.extend([" "] * (anchor - len(line_chars) + 1))
                line_chars[anchor] = theme.color_char("╭", seg.color_code)
                base = "".join(line_chars).rstrip()
                text_lines = seg.pointer.message.splitlines() or [""]
                first, *rest = text_lines
                colored_section = theme.color_char(f"─ {first}", seg.color_code)
                lines.append(f"{base}{colored_section}")
                if rest:
                    continuation = " " * (anchor + 3)
                    for chunk in rest:
                        lines.append(theme.color_char(f"{continuation}{chunk}", seg.color_code))
                active.append((anchor, seg.color_code))
        return lines
    
    @staticmethod
    def _zero_pattern(run_segments:list[_Segment], placement:PointerPlacement, theme:ColorTheme) -> list[str]:
        count = len(run_segments)
        if count == 0:
            return []
        chars:list[str] = []
        if placement == "below":
            chars.append(theme.color_char("╱", run_segments[0].color_code))
            if count > 1:
                for seg in run_segments[1:]:
                    chars.append(theme.color_char("╳", seg.color_code))
            chars.append(theme.color_char("╲", run_segments[-1].color_code))
        else:
            chars.append(theme.color_char("╲", run_segments[0].color_code))
            if count > 1:
                for seg in run_segments[1:]:
                    chars.append(theme.color_char("╳", seg.color_code))
            chars.append(theme.color_char("╱", run_segments[-1].color_code))
        return chars
    
    @staticmethod
    def _segments_width(segments:list[_Segment]) -> int:
        width = 0
        zeros = sorted(seg.start_col for seg in segments if seg.render_pointer and seg.is_zero_width)
        if zeros:
            run_start = zeros[0]
            run_len = 1
            prev = zeros[0]
            for col in zeros[1:]:
                if col <= prev + 1:
                    run_len += 1
                else:
                    width = max(width, run_start + run_len)
                    run_start = col
                    run_len = 1
                prev = col
            width = max(width, run_start + run_len)
        for seg in segments:
            if not seg.render_pointer:
                continue
            if seg.is_zero_width:
                width = max(width, seg.start_col + 1)
                if seg.show_anchor:
                    width = max(width, seg.anchor_col + 1)
            else:
                width = max(width, seg.end_col)
                if seg.show_anchor:
                    width = max(width, seg.anchor_col + 1)
        return width
    
    def throw(self) -> NoReturn:
        raise ReportException(self)

@dataclass
class Error(Report):
    severity:Literal["error"] = field(default="error", init=False)

@dataclass
class Warning(Report):
    severity:Literal["warning"] = field(default="warning", init=False)

@dataclass
class Info(Report):
    severity:Literal["info"] = field(default="info", init=False)

@dataclass
class Hint(Report):
    severity:Literal["hint"] = field(default="hint", init=False)



class ReportException(Exception):
    """Exception raised when a Report is thrown. Contains the report for handling."""
    def __init__(self, report: Report) -> None:
        self.report = report
        super().__init__(str(report))


def main() -> None:
    from textwrap import dedent
    
    print_src = "printl'Hello, World'"
    print_sf = SrcFile.from_text(print_src, "path/to/file.dewy")

    e = Error(
        srcfile=print_sf,
        title="dewy.errors.E1234 (link)",
        message="Unable to juxtapose identifier and string",
        pointer_messages=[
            Pointer(
                span=Span(6, 6),
                message="tried to juxtapose printl (string:>void) and 'Hello, World' (string)\nexpected whitespace or operator between identifier and string",
            ),
        ],
        hint="insert a space or an operator",
    )
    print(e, end="\n\n")
    
    e = Error(
        srcfile=print_sf,
        title="dewy.errors.E2234 (link)",
        message="Token needs additional context",
        pointer_messages=[
            Pointer(
                span=Span(0, 6),
                message="<per token message>",
            ),
        ],
        hint="<some helpful hint>",
    )
    print(e, end="\n\n")
    
    e = Error(
        srcfile=print_sf,
        title="dewy.errors.E2234 (link)",
        message="Highlight multiple adjacent tokens",
        pointer_messages=[
            Pointer(span=Span(0, 6), message="<message about the identifier token>"),
            Pointer(span=Span(6, 6), message="<message about the juxtapose token>"),
            Pointer(span=Span(6, len(print_src)), message="<message about the string token>"),
        ],
        hint="<some helpful hint>",
    )
    print(e, end="\n\n")
    
    tight_src = "10x(y)"
    tight_sf = SrcFile.from_text(tight_src, "path/to/file.dewy")
    e = Error(
        srcfile=tight_sf,
        title="dewy.errors.E3234 (link)",
        message="Dealing with tightly packed tokens",
        pointer_messages=[
            Pointer(span=Span(0, 2), message="<message about the `10` token>"),#, placement="above"),
            Pointer(span=Span(2, 3), message="<message about the `x` token>"),#, placement="above"),
            Pointer(span=Span(3, 4), message="<message about the `(` token>"),#, placement="above"),
            Pointer(span=Span(4, 5), message="<message about the `y` token>"),#, placement="above"),
            Pointer(span=Span(5, 6), message="<message about the `)` token>"),#, placement="above"),
            Pointer(span=Span(2, 2), message="<message about the 10x juxtaposition>"),#, placement="below"),
            Pointer(span=Span(3, 3), message="<message about the x(y) juxtaposition>"),#, placement="below"),
        ],
        hint="<some helpful hint>",
    )
    print(e, end="\n\n")
    
    e = Error(
        srcfile=tight_sf,
        title="dewy.errors.E3234 (link)",
        message="Flipping pointer directions",
        pointer_messages=[
            Pointer(span=Span(2, 2), message="<message about the 10x juxtaposition>"),#, placement="above"),
            Pointer(span=Span(3, 3), message="<message about the x(y) juxtaposition>"),#, placement="above"),
            Pointer(span=Span(0, 2), message="<message about the `10` token>"),#, placement="below"),
            Pointer(span=Span(2, 3), message="<message about the `x` token>"),#, placement="below"),
            Pointer(span=Span(3, 4), message="<message about the `(` token>"),#, placement="below"),
            Pointer(span=Span(4, 5), message="<message about the `y` token>"),#, placement="below"),
            Pointer(span=Span(5, 6), message="<message about the `)` token>"),#, placement="below"),
        ],
        hint="<some helpful hint>",
    )
    print(e, end="\n\n")
    
    multi_src = "10x(y)\n* 42 + 3^x"
    multi_sf = SrcFile.from_text(multi_src, "path/to/file.dewy")
    multi_pointers = [
        Pointer(span=Span(2, 2), message="<message about the 10x juxtaposition>"),#, placement="above"),
        Pointer(span=Span(3, 3), message="<message about the x(y) juxtaposition>"),#, placement="above"),
        Pointer(span=Span(0, 2), message="<message about the `10` token>"),#, placement="below"),
        Pointer(span=Span(2, 3), message="<message about the `x` token>"),#, placement="below"),
        Pointer(span=Span(3, 4), message="<message about the `(` token>"),#, placement="below"),
        Pointer(span=Span(4, 5), message="<message about the `y` token>"),#, placement="below"),
        Pointer(span=Span(5, 6), message="<message about the `)` token>"),#, placement="below"),
        Pointer(span=Span(7, 8), message="<message about the `*` token>"),
        Pointer(span=Span(9, 11), message="<message about the `42` token>"),
        Pointer(span=Span(12, 13), message="<message about the `+` token>"),
        Pointer(span=Span(14, 15), message="<message about the `3` token>"),
        Pointer(span=Span(15, 16), message="<message about the `^` token>"),
        Pointer(span=Span(16, 17), message="<message about the `x` token>"),
    ]
    e = Error(
        srcfile=multi_sf,
        title="dewy.errors.E3234 (link)",
        message="Multi-line expression pointers",
        pointer_messages=multi_pointers,
        hint="<some helpful hint>",
    )
    print(e, end='\n\n')
    
    e = Error(
        srcfile=multi_sf,
        title="dewy.errors.E3234 (link)",
        message="Upper line pointers above, lower line below",
        pointer_messages=[
            Pointer(span=Span(0, 2), message="<message about the `10` token>"),
            Pointer(span=Span(2, 3), message="<message about the `x` token>"),
            Pointer(span=Span(3, 4), message="<message about the `(` token>"),
            Pointer(span=Span(4, 5), message="<message about the `y` token>"),
            Pointer(span=Span(5, 6), message="<message about the `)` token>"),
            Pointer(span=Span(7, 8), message="<message about the `*` token>"),
            Pointer(span=Span(9, 11), message="<message about the `42` token>"),
            Pointer(span=Span(12, 13), message="<message about the `+` token>"),
            Pointer(span=Span(14, 15), message="<message about the `3` token>"),
            Pointer(span=Span(15, 16), message="<message about the `^` token>"),
            Pointer(span=Span(16, 17), message="<message about the `x` token>"),
        ],
        hint="<some helpful hint>",
    )
    print(e, end="\n\n")


    triple_tight_src = "[a]5x(y)"
    triple_tight_sf = SrcFile.from_text(triple_tight_src, "path/to/file.dewy")
    e = Error(
        srcfile=triple_tight_sf,
        title="dewy.errors.E3234 (link)",
        message="Triple tightly packed tokens",
        pointer_messages=[
            Pointer(span=Span(0, 1), message="<message about the `[` token>"),#, placement="above"),
            Pointer(span=Span(1, 2), message="<message about the `a` token>"),#, placement="above"),
            Pointer(span=Span(2, 3), message="<message about the `]` token>"),#, placement="above"),
            Pointer(span=Span(3, 4), message="<message about the `5` token>"),#, placement="above"),
            Pointer(span=Span(4, 5), message="<message about the `x` token>"),#, placement="above"),
            Pointer(span=Span(5, 6), message="<message about the `(` token>"),#, placement="above"),
            Pointer(span=Span(6, 7), message="<message about the `y` token>"),#, placement="above"),
            Pointer(span=Span(7, 8), message="<message about the `)` token>"),#, placement="above"),
            Pointer(span=Span(3, 3), message="<message about the `[a]5` juxtaposition>"),#, placement="below"),
            Pointer(span=Span(4, 4), message="<message about the `5x` juxtaposition>"),#, placement="below"),
            Pointer(span=Span(5, 5), message="<message about the `x(y)` juxtaposition>"),#, placement="below"),
        ],
        hint="<some helpful hint>",
    )
    print(e, end="\n\n")


    e = Error(
        srcfile=triple_tight_sf,
        title="dewy.errors.E3234 (link)",
        message="Unpositioned triple tightly packed tokens",
        pointer_messages=[
            Pointer(span=Span(0, 1), message="<message about the `[` token>"),
            Pointer(span=Span(1, 2), message="<message about the `a` token>"),
            Pointer(span=Span(2, 3), message="<message about the `]` token>"),
            Pointer(span=Span(3, 4), message="<message about the `5` token>"),
            Pointer(span=Span(4, 5), message="<message about the `x` token>"),
            Pointer(span=Span(5, 6), message="<message about the `(` token>"),
            Pointer(span=Span(6, 7), message="<message about the `y` token>"),
            Pointer(span=Span(7, 8), message="<message about the `)` token>"),
            Pointer(span=Span(3, 3), message="<message about the `[a]5` juxtaposition>"),
            Pointer(span=Span(4, 4), message="<message about the `5x` juxtaposition>"),
            Pointer(span=Span(5, 5), message="<message about the `x(y)` juxtaposition>"),
        ],
        hint="<some helpful hint>",
    )
    print(e, end="\n\n")


    
    tri_src = "alpha beta\ngamma + delta\nepsilon & zeta"
    tri_sf = SrcFile.from_text(tri_src, "path/to/file.dewy")
    tri_pointers = [
        Pointer(span=Span(0, 5), message="<message about alpha>"),
        Pointer(span=Span(6, 10), message="<message about beta>"),
        Pointer(span=Span(11, 16), message="<message about gamma>"),
        Pointer(span=Span(17, 18), message="<message about `+`>"),
        Pointer(span=Span(19, 24), message="<message about delta>"),
        Pointer(span=Span(25, 32), message="<message about epsilon>"),
        Pointer(span=Span(33, 34), message="<message about `&`>"),
        Pointer(span=Span(35, 39), message="<message about zeta>"),
    ]
    e = Error(
        srcfile=tri_sf,
        title="dewy.errors.E4000 (link)",
        message="Three-line spanning diagnostic",
        pointer_messages=tri_pointers,
        hint="defaults to showing all markers below for 3+ lines",
    )
    print(e, end="\n\n")
    
    multiline_block_src = "block start {\n  inner stuff\n} block end"
    multiline_block_sf = SrcFile.from_text(multiline_block_src, "path/to/block.dewy")
    full_span = Span(0, len(multiline_block_src))
    e = Error(
        srcfile=multiline_block_sf,
        title="dewy.errors.E6000 (link)",
        message="Illustrate multi-line span pointer",
        pointer_messages=[
            Pointer(
                span=full_span,
                message="<message covering the entire block>",
            ),
        ],
        hint="multi-line spans draw a single pointer after the block",
    )
    print(e, end="\n\n")
    
    long_src = dedent("""\
        step 01: fetch inputs
        step 02: decode config
        step 03: allocate buffers
        step 04: parse stream
        step 05: transform blocks
        step 06: stage outputs
        step 07: compute checksum
        step 08: sign payload
        step 09: finalize partial sum
        step 10: verify outputs
        step 11: cleanup temp files
        step 12: shutdown services
    """)
    long_sf = SrcFile.from_text(long_src, "path/to/long_example.dewy")
    
    def span_cols(line_no:int, start:int, stop:int) -> Span:
        base = long_sf._line_starts[line_no - 1]
        return Span(base + start, base + stop)
    
    def span_text(line_no:int, snippet:str) -> Span:
        row = line_no - 1
        line_text = long_sf.line_text(row)
        offset = line_text.index(snippet)
        return span_cols(line_no, offset, offset + len(snippet))
    
    e = Error(
        srcfile=long_sf,
        title="dewy.errors.E5000 (link)",
        message="Demonstrate multi-digit line numbers",
        pointer_messages=[
            Pointer(span=span_text(9, "finalize"), message="<message on line 9>"),#, placement="above"),
            Pointer(span=span_text(10, "verify outputs"), message="<message on line 10>"),
            Pointer(span=span_text(12, "shutdown services"), message="<message on line 12>"),#, placement="below"),
        ],
        hint="line numbers stay aligned even after 9",
    )
    print(e, end="\n\n")
    
    
    py_src = dedent("""\
        def repeat(message: str, times: int) -> str:
            return message * times

        result = repeat("hello", "3")
        print(result)
    """)

    e = Error(
        srcfile=SrcFile.from_text(py_src, "path/to/py_example.py"),
        title="type mismatch for argument `times`",
        # message="Called `repeat` with 'str' instead of 'int' for argument `times`",
        pointer_messages=[
            Pointer(span=Span(82, 88), message="`repeat` function's second argument `times` expects an 'int'"),
            Pointer(span=Span(98, 101), message="argument given is type 'str'"),
        ],
        hint='Consider changing string literal "3" to integer 3',
    )
    print(e)


if __name__ == "__main__":
    main()