from pathlib import Path

from tools.compiler.census import counts, sites


def test_census_counts_imported_sites_once_and_separates_test_exit(tmp_path):
    first = tmp_path / 'tests/cases/demo/first.dewy'
    first.parent.mkdir(parents=True)
    first.write_text('main=()=>exit(run())\n'
                     'exit(count + 3)\n'
                     'printl(count as uint8)\n')
    common = '../common.dewy:4:2: runtime check: the exact sum of `xs` fits `int64` ($runtime_checks)'
    exit_fit = 'first.dewy:1:15: runtime check: `run() <=? 255` for the conversion to uint8 ($runtime_checks)'
    exit_sum = 'first.dewy:2:6: runtime check: `count + 3 <=? 255` for the conversion to uint8 ($runtime_checks)'
    other_fit = 'first.dewy:3:8: runtime check: `count <=? 255` for the conversion to uint8 ($runtime_checks)'
    mask = 'first.dewy:2:3: runtime check: array shape/index contract `mask.length =? data.length` ($prototype)'
    records = [
        dict(path='tests/cases/demo/first.dewy', rc=0, stdout='\n'.join([common, exit_fit, exit_sum, other_fit, mask])),
        dict(path='tests/cases/demo/second.dewy', rc=0, stdout=common),
        dict(path='tests/cases/demo/bad.dewy', rc=1, stdout=common.replace('4:2', '9:4')),
    ]
    found = sites(records, tmp_path)
    imported = next(programs for (path, _, _, _), programs in found.items() if path.name == 'common.dewy')
    assert imported == {Path(record['path']) for record in records[:2]}
    assert counts(found, tmp_path) == {
        'fixed-width arithmetic': 1,
        'test exit narrowing': 2,
        'integer fit conversion': 1,
        'array shape/index contract': 1,
    }
