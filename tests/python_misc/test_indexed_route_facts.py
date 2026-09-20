"""Repeated constant projections share facts, until a containing write occurs."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute


def source(body, helpers=''):
    return SrcFile(None, helpers + '''
read=(rows:array<array<int64>>):>int64=>{
    if rows.length <? 2 return 0
    if rows[0].length =? 0 return 0
''' + body + '\n}\nmain=():>int64=>read([[42] [7]])')


@pytest.mark.parametrize('body', [
    'return rows[0][0]',
    'let saved=rows[0][0] rows[0]=[] return saved',
    'rows[0]=[] if rows[0].length=?0 return 42 return rows[0][0]',
])
def test_guarded_constant_projection(body):
    codegen(source(body))


@pytest.mark.parametrize('mutation', [
    'rows[0]=[]',
    'rows[1]=[]',  # deliberately conservative: no disjoint-element proof yet
    'rows.clear()',
    'rows.truncate(0)',
    'rows.pop(0);',
    'rows.insert([] 0)',
    'rows=[[] [7]]',
    'erase(@rows)',
    'erase_row(@rows[0])',
])
def test_container_mutations_invalidate_indexed_evidence(mutation):
    helpers = ('erase=(@rows:array<array<int64>>):>void=>{rows[0]=[]}\n'
               'erase_row=(@row:array<int64>):>void=>{row.clear()}\n')
    with pytest.raises(ReportException, match='bound|index'):
        codegen(source(mutation + '\nreturn rows[0][0]', helpers))


def test_index_evaluation_can_invalidate_the_guard():
    helpers = 'erase=(@rows:array<array<int64>>):>0=>{rows[0]=[] return 0}\n'
    with pytest.raises(ReportException, match='bound|index'):
        codegen(source('return rows[erase(@rows)][0]', helpers))


def test_indexed_routes_execute(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'fixtures/indexed_route_facts.dewy'
    execute(tmp_path, 'indexed_routes', codegen(SrcFile.from_path(path), debug_locations=False))


def test_different_index_does_not_inherit_the_guard():
    with pytest.raises(ReportException, match='bound|index'):
        codegen(source('return rows[1][0]'))
