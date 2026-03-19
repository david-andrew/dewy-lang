from argparse import ArgumentParser
from os import PathLike
from pathlib import Path
import re

from PIL import Image


ICON_MAGIC = 0x55444557_5949434F
ICON_FORMAT_VERSION = 0x00000001_00000001
PIXELS_PER_WORD = 2
WORDS_PER_LINE = 8


def normalize_symbol_name(name: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_")
    if not normalized:
        normalized = "icon"
    if normalized[0].isdigit():
        normalized = f"icon_{normalized}"
    return normalized.upper()


def derive_symbol_name(stem: str) -> str:
    return normalize_symbol_name(stem)


def format_word(word: int) -> str:
    upper = (word >> 32) & 0xFFFF_FFFF
    lower = word & 0xFFFF_FFFF
    return f"0x{upper:08x}_{lower:08x}"


def pack_pixels(rgba_bytes: bytes) -> list[int]:
    pixels = [
        int.from_bytes(rgba_bytes[index : index + 4], "big")
        for index in range(0, len(rgba_bytes), 4)
    ]
    packed_words: list[int] = []
    for index in range(0, len(pixels), PIXELS_PER_WORD):
        first = pixels[index]
        second = pixels[index + 1] if index + 1 < len(pixels) else 0
        packed_words.append((first << 32) | second)
    return packed_words


def render_icon_module(
    *,
    symbol_name: str,
    width: int,
    height: int,
    packed_words: list[int],
    source_path: Path,
) -> str:
    lines = [
        f"# Generated from {source_path.name} by generate_udewy_icon.py.",
        "",
        f"const {symbol_name}:array<uint64> = [",
        f"    {format_word(ICON_MAGIC)}",
        f"    {format_word(ICON_FORMAT_VERSION)}",
        f"    {width}",
        f"    {height}",
        f"    {len(packed_words)}",
    ]
    for offset in range(0, len(packed_words), WORDS_PER_LINE):
        chunk = packed_words[offset : offset + WORDS_PER_LINE]
        lines.append(f"    {' '.join(format_word(word) for word in chunk)}")
    lines.extend(
        [
            "]",
            "",
        ]
    )
    return "\n".join(lines)


def generate_icon_module(
    input_image: PathLike,
    output_udewy: PathLike,
    *,
    symbol_name: str | None = None,
) -> Path:
    input_image = Path(input_image)
    output_udewy = Path(output_udewy)
    symbol_name = derive_symbol_name(output_udewy.stem) if symbol_name is None else normalize_symbol_name(symbol_name)

    with Image.open(input_image) as image:
        rgba_image = image.convert("RGBA")
        width, height = rgba_image.size
        packed_words = pack_pixels(rgba_image.tobytes())

    output_udewy.parent.mkdir(parents=True, exist_ok=True)
    output_udewy.write_text(
        render_icon_module(
            symbol_name=symbol_name,
            width=width,
            height=height,
            packed_words=packed_words,
            source_path=input_image,
        )
    )
    return output_udewy


def build_argument_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Generate a packed udewy icon-data module from an image.")
    parser.add_argument("input_image", type=Path, help="Path to the source image.")
    parser.add_argument(
        "output_udewy",
        type=Path,
        nargs="?",
        help="Optional path to the generated .udewy module. Defaults to the input filename with a .udewy extension.",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Optional exported symbol name. Defaults to the output filename stem in uppercase, without the extension.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    output_udewy = args.output_udewy
    if output_udewy is None:
        output_udewy = args.input_image.with_suffix(".udewy")
    output_path = generate_icon_module(args.input_image, output_udewy, symbol_name=args.symbol)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
