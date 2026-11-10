"""Give whole-compiler differentials a diagnostic exit with a distinctive status."""
import re


def diagnostic_status(modules, name='fatal', status=41):
    assert name in ('fatal', 'ice')
    params = '_p:int64 msg:string' if name == 'fatal' else 'msg:string'
    replacement = f'{name}=({params}):>never=>{{printl(msg); exit({status})}}'
    modules['diagnostic_exit.dewy'], count = re.subn(
        rf'(?ms)^{name}=.*?^}}', lambda _: replacement,
        modules['diagnostic_exit.dewy'], count=1)
    assert count == 1, name
