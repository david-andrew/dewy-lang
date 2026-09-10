"""Record names use the carried brand through family and structure views."""
import test_bootstrap_check as source_values

CASES = [
    'T:type=[x:int64]\nT.typename',
    'T:type=[x:int64]\nT[1].typename',
    'T:type=[x:int64 name=()=>typename]\nT[1].name',
    'T=type of [x:int64]\nT.typename',
    'T=type of [x:int64]\nT[1].typename',
    'Root=$abstract type of [x:int64 name=()=>typename]\nChild=type of Root\nChild[1].name',
    'Root=$abstract type of [x:int64]\nChild=type of Root\nlet p:Root=Child[1]\np.typename',
    'Root=$abstract type of [x:int64]\nChild=type of Root\nGrandchild=type of Child\nlet p:Root=Grandchild[1]\np.typename',
    'T=type of [x:int64]\nlet p:[x:int64]=T[1]\np.typename',
    'T:type=[typename:string]\nT["custom"].typename',
]


def test_native_record_type_names(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', [])
    source_values.test_native_source_values(tmp_path)
