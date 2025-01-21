
from mkdocstrings_handlers.zstd.handler import ZstdHandler

def symbol_smoke_test(handler: ZstdHandler, name: str):
    item = handler.collect(name, {})
    html = handler.render(item, {})
    assert html


def test_handler_smoke(handler: ZstdHandler):
    symbols = [
        "MACRO1",
        "func1",
        "enum1",
        "s1",
        "u1",
        "g1",
        "x",
        "G1_MACRO",
        "g1_enum",
        "g1_struct",
        "g1_union",
        "g1_func",
        "func_in_para_returns",
        "var_list_items",
        "var_brief",
        "var_brief_and_detailed",
    ]
    for symbol in symbols:
        symbol_smoke_test(handler, symbol)