from pathlib import Path
from argparse import ArgumentParser
from .targets import TARGETS


def get_version() -> str:
    """Return the semantic version of the language"""
    return (Path(__file__).parents[2] / 'VERSION').read_text().strip()


argparse = ArgumentParser(description='Dewy Compiler')
argparse.add_argument('file', nargs='?', help='.dewy file to run. If not provided, enter REPL mode')
argparse.add_argument('-t', '--target', choices=TARGETS, help='backend target the program should compile to.')
argparse.add_argument('-v', '--version', action='version', version=f'dewy {get_version()}', help='Print version information and exit')

args = argparse.parse_args()

print(args)