import importlib

import pit.importer.sg_api as sg_api
from tests.importer.fakes import FakeSG


def test_importing_sg_api_does_not_load_clr():
    # Reimport must not raise / must not require pythonnet at import time.
    importlib.reload(sg_api)
    assert hasattr(sg_api, "init_sg")
    assert hasattr(sg_api, "SG")


def test_fake_sg_records_calls():
    sg = FakeSG()
    model = sg.sim.Create("RICS")
    sg.sim.Save("out.bhs")
    names = [c[0] for c in sg.calls]
    assert "sim.Create" in names
    assert "sim.Save" in names
