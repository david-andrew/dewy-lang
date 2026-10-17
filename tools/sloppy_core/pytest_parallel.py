"""Keep compact-core compilation batches together without pinning a whole file.

Loaded explicitly by the compact-core gate with pytest-xdist's loadgroup mode.
Other repository tests retain file isolation for their shared build artifacts.
"""
import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.get_closest_marker('xdist_group') is not None:
            continue
        name = item.path.name
        group = str(item.path)
        if name.startswith('test_sloppy_core') or name == 'test_core_dev.py':
            owner = item.getparent(pytest.Class)
            if owner is not None:
                group = owner.nodeid
            else:
                group += f'::{getattr(item, "originalname", item.name)}'
                callspec = getattr(item, 'callspec', None)
                if callspec is not None:
                    for mode in ('target', 'release'):
                        if mode in callspec.params:
                            group += f'::{mode}={callspec.params[mode]}'
        item.add_marker(pytest.mark.xdist_group(name=group))
