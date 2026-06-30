"""In-memory stand-in for the Moody's SG boundary, for tests with no .NET."""
from __future__ import annotations


class _FakeModel:
    def __init__(self, sg, name="", type_name=""):
        self._sg = sg
        self.Name = name
        self._type_name = type_name  # Extension: carry the type so GetType().Name is accurate
        self._params = {}
        self._children = {}

    def AddModel(self, type_name):
        self._sg.calls.append(("model.AddModel", (self.Name, type_name)))
        child = _FakeModel(self._sg, type_name=type_name)
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
        # Extension: return the actual type_name passed to AddModel so that
        # import_models() can discriminate type correctly (e.g. "Economy" vs "MPR").
        # Previously this hardcoded "Economy", which would cause spurious type-mismatch
        # warnings if models of other types were ever looked up by name.
        return type("T", (), {"Name": self._type_name or "Economy"})


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

    def _register_names_from_csv(self, csv_path, type_name=""):
        """
        Extension: read Name column from *csv_path* and register each unique
        issuer (first dotted segment of the Name) in _FakeSim._models so that
        subsequent sim.FindModelByName() calls succeed.

        This is necessary because the real pipeline calls BulkImporter.Import
        and then immediately retries FindModelByName in a loop waiting for the
        async result; with a plain FakeSG the loop would spin 10 × 1 s and then
        return no issuers, causing import_GCP_nonagency_mbs to exit early before
        child-model or parameter-set processing — and before sim.Save is reached.
        """
        try:
            import csv
            with open(csv_path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    raw = (row.get("Name") or "").strip()
                    if not raw:
                        continue
                    # For issuer-level files the Name is the issuer; for child
                    # files it is "ISSUER.BondId" — register only the issuer part.
                    issuer_name = raw.split(".")[0]
                    if issuer_name and issuer_name not in self._sg.sim._models:
                        model = _FakeModel(self._sg, name=issuer_name, type_name=type_name)
                        self._sg.sim._models[issuer_name] = model
        except Exception:
            pass  # Never let fake infrastructure break a test

    def Import(self, parent, type_name, csv_path=None, *rest):
        self._sg.calls.append(("BulkImporter.Import", (parent, type_name, csv_path) + rest))
        if csv_path:
            self._register_names_from_csv(csv_path, type_name=str(type_name))

    def ImportAsync(self, parent, type_name, csv_path=None, *rest):
        self._sg.calls.append(("BulkImporter.ImportAsync", (parent, type_name, csv_path) + rest))
        if csv_path:
            self._register_names_from_csv(csv_path, type_name=str(type_name))


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
