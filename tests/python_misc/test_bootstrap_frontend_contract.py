from pathlib import Path

from udewy import t1


ROOT = Path(__file__).parents[2]
BOOTSTRAP = ROOT / "udewy" / "bootstrap"


def _bootstrap_token_names() -> list[str]:
    names: list[str] = []
    for line in (BOOTSTRAP / "tokens.udewy").read_text().splitlines():
        line = line.strip()
        if line.startswith("const TK_") or line.startswith("const _TK_"):
            names.append(line.split(":", 1)[0].split()[1])
    return names


def test_bootstrap_token_order_matches_python_tokenizer() -> None:
    assert _bootstrap_token_names() == [kind.name for kind in t1.Kind]


def test_bootstrap_tokenizer_declares_python_keywords_and_symbols() -> None:
    source = (BOOTSTRAP / "t0.udewy").read_text()

    for keyword in t1.KEYWORD_TOKENS:
        assert f'map_set(keywords "{keyword}"' in source

    for symbol, kind in t1.SYMBOL_TOKENS:
        assert symbol in source
        assert kind.name in source


def test_bootstrap_loader_requires_path_import_form() -> None:
    source = (BOOTSTRAP / "t0.udewy").read_text()

    assert 'let import_str:int = "import"' in source
    assert "__load_u8__(src + idx) not=? 112" in source
    assert "Expected path string after import" in source
    assert 'import p"tokens.udewy"' in source
