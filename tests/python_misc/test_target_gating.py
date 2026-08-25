from pathlib import Path

import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import UserError


def _check_file(path: Path, target: str = 'x86_64') -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile.from_path(path), include_prelude=False, target=target)
    assert isinstance(root, hir.Block)
    return root


def test_target_metatag_folds_to_a_string() -> None:
    root = check.typecheck_and_resolve(
        SrcFile(None, 'let t = $target let same = $target =? "x86_64" let other = $target =? "wasm32"'),
        target='x86_64',
    )
    declared = {item.name: item for item in root.items if isinstance(item, hir.Declare)}
    assert isinstance(declared['t'].expr, hir.TargetString) and declared['t'].expr.content == 'x86_64'
    assert isinstance(declared['same'].expr, hir.TargetBool) and declared['same'].expr.value is True
    assert isinstance(declared['other'].expr, hir.TargetBool) and declared['other'].expr.value is False


def test_gated_import_binds_only_for_the_matching_target(tmp_path: Path) -> None:
    (tmp_path / 'native_layer.dewy').write_text('let layer_name = "native"\n')
    (tmp_path / 'main.dewy').write_text(
        'if $target =? "x86_64" { from p"native_layer.dewy" import layer_name }\n'
        'if $target =? "wasm32" { from p"does_not_exist.dewy" import nothing }\n'
        'let chosen = layer_name\n'
    )
    root = _check_file(tmp_path / 'main.dewy')
    names = [item.name for item in root.items if isinstance(item, hir.Declare)]
    assert 'chosen' in names  # the gated import bound `layer_name` at module scope


def test_literal_conditions_keep_every_arm_checked() -> None:
    # Only `$target` comparisons gate; `if false` still typechecks its arm.
    with pytest.raises(UserError, match='undefined identifier'):
        check.typecheck_and_resolve(
            SrcFile(None, '$no_prelude = true\nif false { let y = missing }\n'),
            target='x86_64',
        )


def test_supported_targets_rejects_other_targets(tmp_path: Path) -> None:
    # `$no_prelude` keeps the prelude (which has no wasm32 output layer yet) out of it.
    (tmp_path / 'gated.dewy').write_text('$no_prelude = true\n$supported_targets = ["wasm32"]\nlet x = 1\n')
    with pytest.raises(UserError, match='does not support target'):
        _check_file(tmp_path / 'gated.dewy', target='x86_64')
    _check_file(tmp_path / 'gated.dewy', target='wasm32')
