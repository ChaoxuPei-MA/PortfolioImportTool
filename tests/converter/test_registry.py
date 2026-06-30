from pit.converter.processors.registry import HandlerContext, get_handler


def test_known_types_have_handlers():
    for dt in ("GC", "GCCRE", "GCRETAIL", "AGENCYMBS"):
        assert get_handler(dt) is not None


def test_unknown_type_returns_none():
    assert get_handler("FOO") is None
    assert get_handler("gc") is None  # registry keys are upper-case


def test_handler_context_fields():
    ctx = HandlerContext(
        start_date="20250630", rics_version="10.6", gcorr_data={},
        params={}, rics_format={}, mapping_data={}, output_dir_granular="C:/out",
    )
    assert ctx.start_date == "20250630"
    assert ctx.output_dir_granular == "C:/out"
