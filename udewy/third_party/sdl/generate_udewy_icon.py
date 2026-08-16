from argparse import ArgumentParser
from os import PathLike
from pathlib import Path
import re

from PIL import Image


ICON_MAGIC = 0x55444557_5949434F
BYTES_PER_LINE = 32


def normalize_symbol_name(name: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_")
    if not normalized:
        normalized = "icon"
    if normalized[0].isdigit():
        normalized = f"icon_{normalized}"
    return normalized.upper()


def derive_symbol_name(stem: str) -> str:
    return normalize_symbol_name(stem)


def format_hex_lines(data: bytes) -> list[str]:
    return [
        f"    {data[offset : offset + BYTES_PER_LINE].hex()}"
        for offset in range(0, len(data), BYTES_PER_LINE)
    ]


def render_icon_module(
    *,
    symbol_name: str,
    width: int,
    height: int,
    rgba_bytes: bytes,
    source_path: Path,
) -> str:
    header = b"".join(
        value.to_bytes(8, "big")
        for value in (
            ICON_MAGIC,
            width,
            height,
        )
    )
    lines = [
        f"# Generated from {source_path.name} by generate_udewy_icon.py.",
        "",
        f'const {symbol_name}:int = 0x"',
        "    # magic, width, height",
        *format_hex_lines(header),
        "    # RGBA pixels in row-major wire order",
        *format_hex_lines(rgba_bytes),
        '"',
        "",
    ]
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
        rgba_bytes = rgba_image.tobytes()

    output_udewy.parent.mkdir(parents=True, exist_ok=True)
    output_udewy.write_text(
        render_icon_module(
            symbol_name=symbol_name,
            width=width,
            height=height,
            rgba_bytes=rgba_bytes,
            source_path=input_image,
        )
    )
    return output_udewy


def build_argument_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Generate a udewy RGBA icon-data module from an image.")
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
