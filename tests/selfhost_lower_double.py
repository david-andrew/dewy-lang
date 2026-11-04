"""Link one lowering leaf or its twin against the real compiler services."""
import json
import re

from tests.support import ROOT


def modules_for(source, output, leaf="lower_group"):
    # Keep the real service graph: this group owns the recursive dispatcher, so
    # stubbing each outward edge would hide the execution we need to compare.
    # Switch only the requested leaf. Other twins are import shims to the live services;
    # otherwise the helper's Jo imports and Dewy's direct imports create two
    # copies of checker state. Double-quoted service imports stay fixed while
    # compare_leaf switches the single-quoted leaf import.
    modules = {p.name: p.read_text() for p in (ROOT / 'compiler').iterdir()
               if p.suffix in ('.jo', '.dewy')}
    for name in list(modules):
        if name.endswith('.jo') and name != leaf + '.jo':
            service_leaf = name[:-3] + '.dewy'
            if service_leaf in modules:
                modules[name] = f'use "{service_leaf}"\n'
    for name, text in list(modules.items()):
        if name.endswith('.jo'):
            modules[name] = re.sub(
                rf"(?m)^((?:use|import) )'((?!{re.escape(leaf)}\.dewy)[^'\n]+\.dewy)'",
                lambda m: m[1] + json.dumps(m[2]), text)
            # Real service modules already resolve their dependencies. Keep the
            # leaf helper from inserting a test-driver initialization cycle.
            modules[name] += "\n# No use 'driver.jo' or use 'checker_resolve.dewy' needed.\n"
    # The generic leaf driver imports type modules before main, changing the
    # cycle's initializer order. Bind existing host records after all module
    # initializers have run, just before entering the compiler pipeline.
    rebind = []
    for name, text in list(modules.items()):
        if not name.endswith('.jo'):
            continue
        bindings = re.findall(r'(?m)^\w+_binding = (\w+_bind\([^\n]+\))$', text)
        if bindings:
            function = 'lower_test_bind_' + name[:-3]
            modules[name] += '\n' + function + ' = ():\n' + ''.join(
                '    ' + call + '\n' for call in bindings)
            rebind.append((name, function))
    modules['main.jo'] = ''.join(f'use "{name}"\n' for name, _ in rebind
                                 if name != 'main.jo') + modules['main.jo']
    command = ', '.join(json.dumps(str(s)) for s in
                        ('leaf-test', 'build', source, '-o', output))
    modules['main.jo'] = modules['main.jo'].replace('main = ():',
        'lower_test_cli = ():\n' + ''.join('    ' + function + '()\n'
                                           for _, function in rebind), 1)
    modules['main.jo'] = modules['main.jo'].replace('    a = args()', f'    a = [{command}]', 1)
    return modules
