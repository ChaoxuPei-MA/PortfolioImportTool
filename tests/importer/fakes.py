"""In-memory stand-in for the Moody's SG boundary, for tests with no .NET."""
from __future__ import annotations


class _FakeModel:
    def __init__(self, sg, name=""):
        self._sg = sg
        self.Name = name
        self._params = {}
        self._children = {}

    def AddModel(self, type_name):
        self._sg.calls.append(("model.AddModel", (self.Name, type_name)))
        child = _FakeModel(self._sg)
        return child

    def SubModel(self, name):
        self._sg.calls.append(("model.SubModel", (self.Name, name)))
        return self._children.get(name)

    def Delete(self):
        self._sg.calls.append(("model.Delete", (self.Name,)))

    def Parameter(self, name):
        self._sg.calls.append(("model.Parameter", (self.Name, name)))
        return self._params.setdefault(name, _FakeParam())

    def Output(self, output_type):
        self._sg.calls.append(("model.Output", (self.Name, output_type)))
        return _FakeOutput()

    def GetType(self):
        return type("T", (), {"Name": "Economy"})


class _FakeParam:
    def __init__(self):
        self.Value = None


class _FakeOutput:
    def AddOutput(self, output):
        return _FakeSelectedOutput()


class _FakeSelectedOutput:
    def __init__(self):
        self.NumberFormat = None


class _FakeSim:
    def __init__(self, sg):
        self._sg = sg
        self._models = {}

    def InitialiseWithLicence(self, *a): self._sg.calls.append(("sim.InitialiseWithLicence", a))
    def Load(self, p): self._sg.calls.append(("sim.Load", (p,)))
    def Create(self, n): self._sg.calls.append(("sim.Create", (n,))); return _FakeModel(self._sg, n)
    def Save(self, p): self._sg.calls.append(("sim.Save", (p,)))
    def AddModel(self, t): self._sg.calls.append(("sim.AddModel", (t,))); return _FakeModel(self._sg)
    def FindModelByName(self, n): self._sg.calls.append(("sim.FindModelByName", (n,))); return self._models.get(n)
    def FindModelByFullyQualifiedName(self, fqn):
        self._sg.calls.append(("sim.FindModelByFullyQualifiedName", (fqn,))); return _FakeModel(self._sg, fqn)
    def FindModels(self, t): self._sg.calls.append(("sim.FindModels", (t,))); return []
    def Parameter(self, n): self._sg.calls.append(("sim.Parameter", (n,))); return _FakeParam()
    def AddOutputFile(self, f): self._sg.calls.append(("sim.AddOutputFile", (f,))); return _FakeOutput()
    def RemoveOutputFile(self, f): self._sg.calls.append(("sim.RemoveOutputFile", (f,)))
    def ImportOutputFiles(self, p, a): self._sg.calls.append(("sim.ImportOutputFiles", (p, a)))


class _FakeBulkImporter:
    def __init__(self, sg): self._sg = sg
    def __call__(self): return self  # BulkImporter() construction
    def Import(self, *a): self._sg.calls.append(("BulkImporter.Import", a))
    def ImportAsync(self, *a): self._sg.calls.append(("BulkImporter.ImportAsync", a))


class _FakeParamSetImporter:
    def __init__(self, sg): self._sg = sg
    def Import(self, *a): self._sg.calls.append(("ParameterSetImporter.Import", a))


class FakeSG:
    """Mirrors pit.importer.sg_api.SG with call-recording fakes."""
    def __init__(self):
        self.calls = []
        self.sim = _FakeSim(self)
        self.BulkImporter = _FakeBulkImporter(self)
        self.ParameterSetImporter = _FakeParamSetImporter(self)
        self.DuplicateImportAction = type("Dup", (), {"Overwrite": "Overwrite"})
        self.String = lambda s: s
        self.File = type("File", (), {"ReadAllLines": staticmethod(lambda p: [])})
