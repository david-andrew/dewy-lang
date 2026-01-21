"""
AmbiguousChain: A DAG-based data structure for tracking multiple possible 
reduction sequences during parsing, with structural sharing of unchanged regions.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterator, overload


# =============================================================================
# Mock Types for Testing
# =============================================================================

@dataclass
class MockAST:
    """Mock AST node for testing."""
    label: str
    children: tuple[Any, ...] = ()
    
    def __repr__(self):
        if self.children:
            return f"{self.label}({', '.join(repr(c) for c in self.children)})"
        return self.label


@dataclass
class MockOp:
    """Mock operator for testing."""
    symbol: str
    
    def __repr__(self):
        return self.symbol


# =============================================================================
# Core Data Structures
# =============================================================================

# ViewSet represents which views a span belongs to
# Empty frozenset is the sentinel for "ALL views"
ViewSet = frozenset[int]
ALL: ViewSet = frozenset()  # empty set means "all views"


@dataclass
class Span[T]:
    """A contiguous sequence of items belonging to specific views."""
    views: ViewSet  # which views include this span (ALL = shared by all)
    items: list[T]
    
    def includes(self, view_id: int) -> bool:
        """Check if this span is part of the given view."""
        return self.views == ALL or view_id in self.views
    
    def __repr__(self):
        views_str = "ALL" if self.views == ALL else f"{set(self.views)}"
        return f"Span({views_str}, {self.items})"


class ChainView[T]:
    """A view into an AmbiguousChain for a specific interpretation."""
    
    def __init__(self, chain: AmbiguousChain[T], view_id: int):
        self._chain = chain
        self._view_id = view_id
    
    @property
    def view_id(self) -> int:
        return self._view_id
    
    def __len__(self) -> int:
        return sum(
            len(span.items) 
            for span in self._chain._spans 
            if span.includes(self._view_id)
        )
    
    @overload
    def __getitem__(self, idx: int) -> T: ...
    @overload
    def __getitem__(self, idx: slice) -> list[T]: ...
    def __getitem__(self, idx: int | slice) -> T | list[T]:
        if isinstance(idx, slice):
            items = self._chain._flatten(self._view_id)
            return items[idx]
        
        if idx < 0:
            idx = len(self) + idx
        
        span_idx, offset = self._chain._locate(self._view_id, idx)
        return self._chain._spans[span_idx].items[offset]
    
    def __setitem__(self, slc: slice, value: list[T]) -> None:
        """Apply a reduction (slice assignment) to this view."""
        self._chain._reduce_view(self._view_id, slc, value)
    
    def mark_ambiguous(self, options: list[tuple[slice, list[T]]]) -> None:
        """
        Split this view into multiple views, one per option.
        Each option is (slice, replacement) representing a different reduction.
        """
        self._chain._mark_ambiguous_view(self._view_id, options)
    
    def __repr__(self):
        items = self._chain._flatten(self._view_id)
        return f"ChainView({self._view_id}, {items})"
    
    def __iter__(self) -> Iterator[T]:
        return iter(self._chain._flatten(self._view_id))
    
    def to_list(self) -> list[T]:
        """Return the items as a plain list."""
        return self._chain._flatten(self._view_id)


class AmbiguousChain[T]:
    """
    A chain of items that can track multiple ambiguous reduction sequences.
    
    Uses a DAG-based span structure where:
    - Spans track which views they belong to
    - Shared spans (ALL) are used for regions unchanged across views
    - View-specific spans diverge at ambiguity points
    """
    
    def __init__(self, items: list[T]):
        # Start with a single span containing all items, shared by all views
        self._spans: list[Span[T]] = [Span(ALL, list(items))]
        self._view_ids: set[int] = {0}  # Start with view 0
        self._next_id: int = 1
    
    @property
    def num_views(self) -> int:
        return len(self._view_ids)
    
    def views(self) -> Iterator[ChainView[T]]:
        """Iterate over all current views."""
        for vid in sorted(self._view_ids):
            yield ChainView(self, vid)
    
    def _flatten(self, view_id: int) -> list[T]:
        """Get the flat list of items for a specific view."""
        result: list[T] = []
        for span in self._spans:
            if span.includes(view_id):
                result.extend(span.items)
        return result
    
    def _locate(self, view_id: int, flat_idx: int) -> tuple[int, int]:
        """
        Map a flat index to (span_index, offset_within_span).
        
        Returns the span index and offset for the item at flat_idx in the given view.
        """
        current = 0
        for i, span in enumerate(self._spans):
            if span.includes(view_id):
                span_len = len(span.items)
                if flat_idx < current + span_len:
                    return (i, flat_idx - current)
                current += span_len
        raise IndexError(f"Index {flat_idx} out of range for view {view_id}")
    
    def _locate_slice(self, view_id: int, slc: slice) -> list[tuple[int, int, int]]:
        """
        Locate all spans touched by a slice in a view.
        
        Returns list of (span_index, start_offset, end_offset) tuples.
        The offsets are within each span's items list.
        """
        length = sum(len(s.items) for s in self._spans if s.includes(view_id))
        start, stop, _ = slc.indices(length)
        
        result = []
        current = 0
        
        for i, span in enumerate(self._spans):
            if not span.includes(view_id):
                continue
            
            span_start = current
            span_end = current + len(span.items)
            
            # Check if this span overlaps with [start, stop)
            if span_end > start and span_start < stop:
                # Calculate the overlap within this span
                overlap_start = max(0, start - span_start)
                overlap_end = min(len(span.items), stop - span_start)
                result.append((i, overlap_start, overlap_end))
            
            current = span_end
            if current >= stop:
                break
        
        return result
    
    def _reduce_view(self, view_id: int, slc: slice, replacement: list[T]) -> None:
        """
        Apply a reduction to a specific view.
        
        This may require splitting shared spans to maintain independence between views.
        """
        affected = self._locate_slice(view_id, slc)
        if not affected:
            return
        
        self._rebuild_after_reduction(view_id, affected, replacement)
    
    def _rebuild_after_reduction(
        self, 
        view_id: int, 
        affected: list[tuple[int, int, int]], 
        replacement: list[T]
    ) -> None:
        """Rebuild spans after a reduction, properly handling shared vs specific."""
        
        first_span_idx = affected[0][0]
        last_span_idx = affected[-1][0]
        first_start_off = affected[0][1]
        last_end_off = affected[-1][2]
        
        first_span = self._spans[first_span_idx]
        last_span = self._spans[last_span_idx]
        
        other_views = self._view_ids - {view_id}
        
        new_spans: list[Span[T]] = []
        
        # Add spans before the affected region (unchanged)
        for i in range(first_span_idx):
            new_spans.append(self._spans[i])
        
        # Handle prefix of first affected span (part before the slice starts)
        if first_start_off > 0:
            prefix_items = first_span.items[:first_start_off]
            if first_span.views == ALL:
                # Keep it shared
                new_spans.append(Span(ALL, prefix_items))
            elif view_id in first_span.views:
                # Split: this view's prefix separate from others
                remaining_views = first_span.views - {view_id}
                if remaining_views:
                    new_spans.append(Span(frozenset(remaining_views), prefix_items.copy()))
                new_spans.append(Span(frozenset({view_id}), prefix_items.copy()))
            else:
                # Shouldn't happen but handle gracefully
                new_spans.append(Span(first_span.views, prefix_items))
        
        # Collect the replaced portion for other views (if needed)
        if other_views:
            other_content: list[T] = []
            for span_idx, start_off, end_off in affected:
                span = self._spans[span_idx]
                # Only include if this span is visible to other views
                if span.views == ALL or (span.views & other_views):
                    # Determine what portion of this span to include
                    if span_idx == first_span_idx:
                        portion = span.items[start_off:end_off]
                    elif span_idx == last_span_idx:
                        portion = span.items[start_off:end_off]
                    else:
                        portion = span.items[start_off:end_off]
                    other_content.extend(portion)
            
            if other_content:
                new_spans.append(Span(frozenset(other_views), other_content))
        
        # Add the replacement for this view
        if replacement:
            new_spans.append(Span(frozenset({view_id}), replacement))
        
        # Handle suffix of last affected span (part after the slice ends)
        if last_end_off < len(last_span.items):
            suffix_items = last_span.items[last_end_off:]
            if last_span.views == ALL:
                # Keep it shared
                new_spans.append(Span(ALL, suffix_items))
            elif view_id in last_span.views:
                # Split: this view's suffix separate from others
                remaining_views = last_span.views - {view_id}
                new_spans.append(Span(frozenset({view_id}), suffix_items.copy()))
                if remaining_views:
                    new_spans.append(Span(frozenset(remaining_views), suffix_items.copy()))
            else:
                new_spans.append(Span(last_span.views, suffix_items))
        
        # Add spans after the affected region (unchanged)
        for i in range(last_span_idx + 1, len(self._spans)):
            new_spans.append(self._spans[i])
        
        self._spans = new_spans
        self._cleanup_spans()
    
    def _cleanup_spans(self) -> None:
        """Remove empty spans and merge adjacent spans with same view set."""
        # Remove empty spans
        self._spans = [s for s in self._spans if s.items]
        
        # Merge adjacent spans with identical view sets
        if len(self._spans) <= 1:
            return
        
        merged: list[Span[T]] = [self._spans[0]]
        for span in self._spans[1:]:
            if merged[-1].views == span.views:
                merged[-1].items.extend(span.items)
            else:
                merged.append(span)
        
        self._spans = merged
    
    def _new_view_id(self) -> int:
        """Generate a new unique view ID."""
        vid = self._next_id
        self._next_id += 1
        return vid
    
    def mark_ambiguous(self, options: list[tuple[slice, list[T]]]) -> None:
        """
        Apply ambiguous reduction to all current views.
        
        Each option is (slice, replacement). Creates len(options) new views
        for each existing view.
        """
        if not options:
            return
        
        # Snapshot current views
        current_views = list(self._view_ids)
        
        for view_id in current_views:
            self._mark_ambiguous_view(view_id, options)
    
    def _mark_ambiguous_view(self, view_id: int, options: list[tuple[slice, list[T]]]) -> None:
        """
        Split a single view into multiple views, one per option.
        
        Uses smart span management to maximize sharing for non-overlapping reductions.
        """
        if not options:
            return
        
        if len(options) == 1:
            # Not really ambiguous, just apply the single reduction
            slc, replacement = options[0]
            self._reduce_view(view_id, slc, replacement)
            return
        
        # Create new view IDs for each option (reuse current for first)
        new_view_ids = [view_id] + [self._new_view_id() for _ in range(len(options) - 1)]
        
        # Update view tracking
        self._view_ids.discard(view_id)
        self._view_ids.update(new_view_ids)
        
        # Calculate the affected ranges for all options
        length = sum(len(s.items) for s in self._spans if s.includes(view_id))
        option_ranges = []
        for slc, _ in options:
            start, stop, _ = slc.indices(length)
            option_ranges.append((start, stop))
        
        # Find the overall affected range (union of all options)
        min_start = min(r[0] for r in option_ranges)
        max_stop = max(r[1] for r in option_ranges)
        
        # Reconstruct spans: prefix (shared), divergent middle (per-view), suffix (shared)
        flat_items = self._flatten(view_id)
        other_views = self._view_ids - set(new_view_ids)
        
        new_spans: list[Span[T]] = []
        
        # Add all spans not related to this view (unchanged)
        for span in self._spans:
            if span.views == ALL:
                # Will handle below
                continue
            if view_id not in span.views:
                new_spans.append(span)
        
        # Handle shared prefix (before any reduction starts)
        if min_start > 0:
            prefix = flat_items[:min_start]
            # Check if this was part of an ALL span
            # For simplicity, create shared span for all new views
            new_spans.append(Span(frozenset(new_view_ids), prefix))
            # If there were other views using ALL spans, they keep access too
            for span in self._spans:
                if span.views == ALL and span.includes(view_id):
                    # Other views that aren't being forked need this prefix too
                    if other_views:
                        new_spans.append(Span(frozenset(other_views), prefix))
                    break
        
        # Create divergent spans for each new view (the reduction results)
        for new_vid, (slc, replacement) in zip(new_view_ids, options):
            start, stop, _ = slc.indices(length)
            # Build this view's version: prefix (within divergent) + replacement + suffix (within divergent)
            local_prefix = flat_items[min_start:start] if start > min_start else []
            local_suffix = flat_items[stop:max_stop] if stop < max_stop else []
            view_items: list[T] = local_prefix + replacement + local_suffix
            new_spans.append(Span(frozenset({new_vid}), view_items))
        
        # For other views (not being forked), preserve the original content in divergent region
        if other_views:
            divergent_content: list[T] = flat_items[min_start:max_stop]
            if divergent_content:
                new_spans.append(Span(frozenset(other_views), divergent_content))
        
        # Handle shared suffix (after all reductions end)
        if max_stop < len(flat_items):
            suffix: list[T] = flat_items[max_stop:]
            new_spans.append(Span(frozenset(new_view_ids), suffix))
            if other_views:
                new_spans.append(Span(frozenset(other_views), suffix))
        
        self._spans = new_spans
        self._cleanup_spans()
    
    def _fork_view(self, original_id: int, new_ids: list[int]) -> None:
        """
        Fork a view into multiple views.
        
        - ALL spans that contain the original view get split into per-view spans
          for the new views (so they can diverge independently)
        - View-specific spans for original_id get duplicated for each new ID
        """
        # Figure out which views are NOT being forked (they keep ALL spans)
        other_views = self._view_ids - {original_id}
        
        # Update _view_ids
        self._view_ids.discard(original_id)
        self._view_ids.update(new_ids)
        
        # Update spans
        new_spans: list[Span[T]] = []
        
        for span in self._spans:
            if span.views == ALL:
                # Split: other views keep a shared version, 
                # each new view gets its own copy
                if other_views:
                    new_spans.append(Span(frozenset(other_views), span.items))
                for new_vid in new_ids:
                    new_spans.append(Span(frozenset({new_vid}), span.items.copy()))
            elif original_id in span.views:
                # This span included the original view
                remaining = span.views - {original_id}
                
                if remaining:
                    # Keep span for other views in this set
                    new_spans.append(Span(frozenset(remaining), span.items))
                
                # Create copies for each new view ID
                for new_vid in new_ids:
                    new_spans.append(Span(frozenset({new_vid}), span.items.copy()))
            else:
                # Span doesn't include original view, keep as is
                new_spans.append(span)
        
        self._spans = new_spans
        self._cleanup_spans()
    
    def __repr__(self):
        return f"AmbiguousChain(views={self._view_ids}, spans={self._spans})"
    
    def debug_str(self) -> str:
        """Return a detailed debug representation."""
        lines = [f"AmbiguousChain with {self.num_views} views:"]
        lines.append(f"  View IDs: {sorted(self._view_ids)}")
        lines.append(f"  Spans ({len(self._spans)}):")
        for i, span in enumerate(self._spans):
            lines.append(f"    [{i}] {span}")
        lines.append("  Flattened views:")
        for vid in sorted(self._view_ids):
            items = self._flatten(vid)
            lines.append(f"    View {vid}: {items}")
        return "\n".join(lines)


# =============================================================================
# Tests
# =============================================================================

def test_basic():
    """Test basic chain creation and view access."""
    a, b, c = MockAST('a'), MockAST('b'), MockAST('c')
    mul, exp = MockOp('*'), MockOp('^')
    
    chain = AmbiguousChain([a, mul, b, exp, c])
    
    assert chain.num_views == 1
    view = next(chain.views())
    assert len(view) == 5
    assert view[0] == a
    assert view[2] == b
    assert view[4] == c
    assert view[1] == mul
    assert view[3] == exp
    
    print("test_basic passed")


def test_simple_reduction():
    """Test a simple non-ambiguous reduction."""
    a, b, c = MockAST('a'), MockAST('b'), MockAST('c')
    mul, exp = MockOp('*'), MockOp('^')
    
    chain = AmbiguousChain([a, mul, b, exp, c])
    view = next(chain.views())
    
    # Reduce a * b -> AST(*, (a, b))
    ast_mul = MockAST('*', (a, b))
    view[0:3] = [ast_mul]
    
    assert len(view) == 3  # [AST(a*b), ^, c]
    assert view[0] == ast_mul
    assert view[1] == exp
    assert view[2] == c
    
    print("test_simple_reduction passed")


def test_ambiguous_reduction():
    """Test creating ambiguous reductions."""
    a, b, c = MockAST('a'), MockAST('b'), MockAST('c')
    mul, exp = MockOp('*'), MockOp('^')
    
    chain = AmbiguousChain([a, mul, b, exp, c])
    
    # Create two possible reductions:
    # Option 0: reduce a*b first -> [AST(a*b), ^, c]
    # Option 1: reduce b^c first -> [a, *, AST(b^c)]
    ast_mul = MockAST('*', (a, b))
    ast_exp = MockAST('^', (b, c))
    
    chain.mark_ambiguous([
        (slice(0, 3), [ast_mul]),  # a * b -> AST(a*b)
        (slice(2, 5), [ast_exp]),  # b ^ c -> AST(b^c)
    ])
    
    assert chain.num_views == 2
    
    views = list(chain.views())
    view0_items = views[0].to_list()
    view1_items = views[1].to_list()
    
    # View 0: [AST(a*b), ^, c]
    assert len(view0_items) == 3
    assert view0_items[0] == ast_mul
    assert view0_items[1] == exp
    assert view0_items[2] == c
    
    # View 1: [a, *, AST(b^c)]
    assert len(view1_items) == 3
    assert view1_items[0] == a
    assert view1_items[1] == mul
    assert view1_items[2] == ast_exp
    
    print("test_ambiguous_reduction passed")


def test_nested_ambiguity():
    """Test ambiguous reduction within a view."""
    a, b, c, d = MockAST('a'), MockAST('b'), MockAST('c'), MockAST('d')
    mul, exp, plus = MockOp('*'), MockOp('^'), MockOp('+')
    
    chain = AmbiguousChain([a, mul, b, exp, c, plus, d])
    
    # First ambiguity
    ast_mul = MockAST('*', (a, b))
    ast_exp = MockAST('^', (b, c))
    
    chain.mark_ambiguous([
        (slice(0, 3), [ast_mul]),
        (slice(2, 5), [ast_exp]),
    ])
    
    assert chain.num_views == 2
    
    # Now, within view 1 (which has [a, *, AST(b^c), +, d]), create another ambiguity
    views = list(chain.views())
    view1 = views[1]  # [a, *, AST(b^c), +, d]
    
    ast_exp2 = MockAST('^', (view1[2], d))
    ast_plus = MockAST('+', (view1[2], d))
    
    view1.mark_ambiguous([
        (slice(2, 5), [ast_exp2]),  # AST(b^c) ^ d (hypothetical)
        (slice(2, 5), [ast_plus]),  # AST(b^c) + d
    ])
    
    assert chain.num_views == 3  # view 0 + 2 new from view 1
    
    print("test_nested_ambiguity passed")


def test_complete_reduction():
    """Test reducing all views to single items."""
    a, b, c = MockAST('a'), MockAST('b'), MockAST('c')
    mul, exp = MockOp('*'), MockOp('^')
    
    chain = AmbiguousChain([a, mul, b, exp, c])
    
    ast_mul = MockAST('*', (a, b))
    ast_exp = MockAST('^', (b, c))
    
    chain.mark_ambiguous([
        (slice(0, 3), [ast_mul]),
        (slice(2, 5), [ast_exp]),
    ])
    
    # Complete reductions for each view
    for view in list(chain.views()):
        items = view.to_list()
        if items[0].label == '*':
            # [AST(a*b), ^, c] -> reduce to AST((a*b)^c)
            final = MockAST('^', (items[0], items[2]))
            view[0:3] = [final]
        else:
            # [a, *, AST(b^c)] -> reduce to AST(a*(b^c))
            final = MockAST('*', (items[0], items[2]))
            view[0:3] = [final]
    
    # All views should now have single item
    results = [v[0] for v in chain.views()]
    assert len(results) == 2
    assert all(len(v) == 1 for v in chain.views())
    
    # Check the results
    labels = {r.label for r in results}
    assert labels == {'^', '*'}
    
    print("test_complete_reduction passed")


def test_shared_suffix():
    """Test that suffixes remain shared after ambiguous reduction."""
    a, b, c, d, e = MockAST('a'), MockAST('b'), MockAST('c'), MockAST('d'), MockAST('e')
    op1, op2, op3 = MockOp('+'), MockOp('*'), MockOp('-')
    
    chain = AmbiguousChain([a, op1, b, op2, c, op3, d, op1, e])
    
    # Create ambiguity in the middle, suffix should stay shared
    ast1 = MockAST('*', (b, c))
    ast2 = MockAST('+', (a, b))
    
    chain.mark_ambiguous([
        (slice(2, 5), [ast1]),  # b * c -> AST
        (slice(0, 3), [ast2]),  # a + b -> AST
    ])
    
    assert chain.num_views == 2
    
    # Check that both views end with the same suffix items
    views = list(chain.views())
    for view in views:
        items = view.to_list()
        # Last items should be d, op1, e
        assert items[-1] == e
        assert items[-3] == d
    
    print("test_shared_suffix passed")


def test_complex_expression():
    """Test with the complex expression from the plan."""
    a, b, c, d, e, f, g, h, i, j = [MockAST(x) for x in 'abcdefghij']
    plus, mul, div, exp = MockOp('+'), MockOp('*'), MockOp('/'), MockOp('^')
    
    # a + b * c / e ^ f + g ^ h * i * j
    chain = AmbiguousChain([
        a, plus, b, mul, c, div, e, exp, f, plus, g, exp, h, mul, i, mul, j
    ])
    
    # First ambiguity: b*c at high prec vs e^f first
    ast_bc = MockAST('*', (b, c))
    ast_ef = MockAST('^', (e, f))
    
    chain.mark_ambiguous([
        (slice(2, 5), [ast_bc]),   # b * c
        (slice(6, 9), [ast_ef]),   # e ^ f
    ])
    
    assert chain.num_views == 2
    
    print("test_complex_expression passed")
    print(chain.debug_str())


def run_all_tests():
    """Run all tests."""
    test_basic()
    test_simple_reduction()
    test_ambiguous_reduction()
    test_nested_ambiguity()
    test_complete_reduction()
    test_shared_suffix()
    test_complex_expression()
    print("\nAll tests passed!")


if __name__ == '__main__':
    run_all_tests()
