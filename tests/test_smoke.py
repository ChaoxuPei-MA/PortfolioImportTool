import pit
from pit.version import __version__


def test_package_imports():
    assert pit is not None


def test_version_is_string():
    assert isinstance(__version__, str)
    assert __version__  # non-empty
