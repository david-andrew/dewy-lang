from pathlib import Path
from ..backend.python import python_interpreter
import pdb

def test_examples():
    current_test_cases = {
        'hello.dewy',
        'hello_func.dewy',
        'hello_name.dewy',
        'hello_loop.dewy',
        'anonymous_func.dewy',
        'if_else.dewy',
        'if_else_if.dewy',
        'dangling_else.dewy',
        'if_tree.dewy',
        'loop_in_iter.dewy',
        'loop_and_iters.dewy',
        'enumerate_list.dewy',
        'loop_or_iters.dewy',
        'nested_loop.dewy',
        'block_printing.dewy',
        # 'fizzbuzz-1.dewy',
    }
    example_root = Path(__file__).parent.parent.parent / 'examples'
    for example_path in example_root.glob('*.dewy'):
        if example_path.name not in current_test_cases:
            continue
        print(f'running {example_path.relative_to(example_root)}')
        python_interpreter(example_path, [])

if __name__ == '__main__':
    test_examples()
