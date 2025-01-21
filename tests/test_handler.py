
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

def test_handler_empty_macro(handler: ZstdHandler):
    item = handler.collect("EMPTY_MACRO", {})
    html = handler.render(item, {})
    assert ">#define EMPTY_MACRO<" in html

def test_handler_simple_macro(handler: ZstdHandler):
    item = handler.collect("SIMPLE_MACRO", {})
    html = handler.render(item, {})
    assert ">#define SIMPLE_MACRO 1<" in html
    
    html = handler.render(item, {"show_define_initializer": False})
    assert ">#define SIMPLE_MACRO<" in html

def test_handler_func_macro(handler: ZstdHandler):
    item = handler.collect("FUNC_MACRO", {})
    html = handler.render(item, {})
    assert ">#define FUNC_MACRO(x) x<" in html
    
    html = handler.render(item, {"show_define_initializer": False})
    assert ">#define FUNC_MACRO(x)<" in html

def test_handler_func_macro_no_args(handler: ZstdHandler):
    item = handler.collect("FUNC_MACRO_NO_ARGS", {})
    html = handler.render(item, {})
    assert ">#define FUNC_MACRO_NO_ARGS() y<" in html