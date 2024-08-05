from ..tokenizer import tokenize
from ..postok import post_process
from ..parser import top_level_parse  # type: ignore[reportShadowedImports]
from ..dewy import Scope, void


def python_interpreter(path: str, args: list[str]):

    with open(path) as f:
        src = f.read()

    tokens = tokenize(src)
    post_process(tokens)

    root = Scope.default()
    ast = top_level_parse(tokens, root)
    res = ast.eval(root)
    if res and res is not void:
        print(res)
