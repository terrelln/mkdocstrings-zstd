from mkdocstrings_handlers.zstd.doxygen import (
    CompoundType,
    DescriptionKind,
    ObjectKind,
    ParameterDirection,
    DescriptionAdmonition,
    DescriptionParagraph,
    DescriptionText,
    DescriptionReturn,
    DescriptionParameter,
    DescriptionList,
)


def test_doxygen_file1(doxygen):
    macro1 = doxygen.collect("MACRO1")
    assert macro1.kind == ObjectKind.DEFINE
    assert macro1.name == "MACRO1"
    assert macro1.value == "x"
    assert len(macro1.parameters) == 1
    assert macro1.parameters[0].type is None
    assert macro1.parameters[0].name == "x"

    func1 = doxygen.collect("func1")
    assert func1.kind == ObjectKind.FUNCTION
    assert func1.name == "func1"
    assert len(func1.parameters) == 2
    assert func1.parameters[0].type == "struct1*"
    assert func1.parameters[0].name == "s"
    assert func1.parameters[1].type == "int"
    assert func1.parameters[1].name == "x"

    enum1 = doxygen.collect("enum1")
    assert enum1.kind == ObjectKind.ENUM
    assert enum1.name == "enum1"
    assert len(enum1.values) == 4
    assert enum1.values[0].name == "enum1_value1"
    assert enum1.values[0].initializer == "= 0"
    assert enum1.values[1].name == "enum1_value2"
    assert enum1.values[1].initializer is None
    assert enum1.values[3].name == "enum1_value5"
    assert enum1.values[3].initializer == "= 5"


def test_doxygen_file2(doxygen):
    macro2 = doxygen.collect("MACRO2")
    assert macro2.kind == ObjectKind.DEFINE
    assert macro2.name == "MACRO2"
    assert macro2.value == "MACRO3(x)"
    assert len(macro2.parameters) == 1
    assert macro2.parameters[0].type is None
    assert macro2.parameters[0].name == "x"

    func2 = doxygen.collect("func2")
    assert func2.kind == ObjectKind.FUNCTION
    assert func2.name == "func2"
    assert len(func2.parameters) == 2
    assert func2.parameters[0].type == "struct2*"
    assert func2.parameters[0].name == "s"
    assert func2.parameters[1].type == "int"
    assert func2.parameters[1].name == "x"

    enum2 = doxygen.collect("enum2")
    assert enum2.kind == ObjectKind.ENUM
    assert enum2.name == "enum2"
    assert len(enum2.values) == 4
    assert enum2.values[0].name == "enum2_value1"
    assert enum2.values[0].initializer == "= 0"
    assert enum2.values[1].name == "enum2_value2"
    assert enum2.values[1].initializer is None
    assert enum2.values[3].name == "enum2_value5"
    assert enum2.values[3].initializer == "= 5"


def test_doxygen_file3(doxygen):
    macro3 = doxygen.collect("MACRO3")
    assert macro3.kind == ObjectKind.DEFINE
    assert macro3.name == "MACRO3"
    assert macro3.value == "MACRO1(x)"
    assert len(macro3.parameters) == 1
    assert macro3.parameters[0].type is None
    assert macro3.parameters[0].name == "x"

    func3 = doxygen.collect("func3")
    assert func3.kind == ObjectKind.FUNCTION
    assert func3.name == "func3"
    assert len(func3.parameters) == 2
    assert func3.parameters[0].type == "struct3*"
    assert func3.parameters[0].name == "s"
    assert func3.parameters[1].type == "int"
    assert func3.parameters[1].name == "x"

    enum3 = doxygen.collect("enum3")
    assert enum3.kind == ObjectKind.ENUM
    assert enum3.name == "enum3"
    assert len(enum3.values) == 4
    assert enum3.values[0].name == "enum3_value1"
    assert enum3.values[0].initializer == "= 0"
    assert enum3.values[1].name == "enum3_value2"
    assert enum3.values[1].initializer is None
    assert enum3.values[3].name == "enum3_value5"
    assert enum3.values[3].initializer == "= 5"


def test_struct(doxygen):
    s = doxygen.collect("s1")
    assert s.kind == ObjectKind.COMPOUND
    assert s.type == CompoundType.STRUCT
    assert s.name == "s1"
    assert len(s.members) == 3

    assert s.members[0].kind == ObjectKind.VARIABLE
    assert s.members[0].type == "int"
    assert s.members[0].name == "x"
    assert s.members[0].qualified_name == "s1::x"

    assert s.members[1].kind == ObjectKind.VARIABLE
    assert s.members[1].type == "enum1"
    assert s.members[1].name == "e"
    assert s.members[1].qualified_name == "s1::e"

    assert s.members[2].kind == ObjectKind.VARIABLE
    assert s.members[2].qualified_name == "s1::y"


def test_union(doxygen):
    u = doxygen.collect("u1")
    assert u.kind == ObjectKind.COMPOUND
    assert u.type == CompoundType.UNION
    assert u.name == "u1"
    assert len(u.members) == 2

    assert u.members[0].kind == ObjectKind.VARIABLE
    assert u.members[0].type == "int"
    assert u.members[0].name == "x"
    assert u.members[0].qualified_name == "u1::x"

    assert u.members[1].kind == ObjectKind.VARIABLE
    assert u.members[1].type == "s1"
    assert u.members[1].name == "s"
    assert u.members[1].qualified_name == "u1::s"


def test_group(doxygen):
    g = doxygen.collect("g1")
    assert g.kind == ObjectKind.COMPOUND
    assert g.type == CompoundType.GROUP
    assert g.name == "g1"
    assert g.title == "Group 1"

    assert g.members[0].kind == ObjectKind.COMPOUND
    assert g.members[0].type == CompoundType.STRUCT
    assert g.members[0].name == "g1_struct"
    assert g.members[0].qualified_name == "g1_struct"

    assert g.members[1].kind == ObjectKind.COMPOUND
    assert g.members[1].type == CompoundType.UNION
    assert g.members[1].name == "g1_union"
    assert g.members[1].qualified_name == "g1_union"
    assert g.members[1].members[0].type == "struct g1_struct"

    assert g.members[2].kind == ObjectKind.ENUM
    assert g.members[2].name == "g1_enum"
    assert g.members[2].qualified_name == "g1_enum"

    assert g.members[3].kind == ObjectKind.VARIABLE
    assert g.members[3].type == "const int"
    assert g.members[3].name == "x"
    assert g.members[3].qualified_name == "x"

    assert g.members[4].kind == ObjectKind.FUNCTION
    assert g.members[4].name == "g1_func"
    assert g.members[4].qualified_name == "g1_func"

    assert g.members[5].kind == ObjectKind.DEFINE
    assert g.members[5].name == "G1_MACRO"
    assert g.members[5].value == "5"
    assert g.members[5].qualified_name == "G1_MACRO"


def test_func_in_para_returns(doxygen):
    func = doxygen.collect("func_in_para_returns")
    desc = func.description

    print(desc)

    expected = DescriptionParagraph(
        contents=[
            DescriptionText(
                contents="This is some inline documentation that goes straight into a return without a newline."
            ),
            DescriptionReturn(
                description=DescriptionParagraph(
                    contents=[DescriptionText(contents="Something with a multiline")]
                ),
                title="Returns",
            ),
            DescriptionAdmonition(
                style="note",
                title="Note",
                contents=DescriptionParagraph(
                    contents=[DescriptionText(contents="This is an important note")]
                ),
            ),
            DescriptionAdmonition(
                style="warning",
                title="Warning",
                contents=DescriptionParagraph(
                    contents=[
                        DescriptionText(contents="Followed by a very important warning")
                    ]
                ),
            ),
            DescriptionText(contents="Finally some text"),
            DescriptionList(
                title="Parameters",
                contents=[
                    DescriptionParameter(
                        name="x",
                        description=DescriptionParagraph(
                            contents=[DescriptionText(contents="This is a param")]
                        ),
                        type="int",
                        direction=None,
                    ),
                    DescriptionParameter(
                        name="y",
                        description=DescriptionParagraph(
                            contents=[DescriptionText(contents="This is another param")]
                        ),
                        type=None,
                        direction=ParameterDirection.OUT,
                    ),
                    DescriptionParameter(
                        name="z",
                        description=DescriptionParagraph(
                            contents=[DescriptionText(contents="Finally a 3rd param")]
                        ),
                        type=None,
                        direction=None,
                    ),
                ],
            ),
            DescriptionText(contents="Followed by some more text"),
        ]
    )
    assert desc == expected


def test_var_list_items(doxygen):
    var = doxygen.collect("var_list_items")
    desc = var.description

    print(desc)
    expected = DescriptionParagraph(
        contents=[
            DescriptionParagraph(
                contents=[
                    DescriptionText(contents="text"),
                    DescriptionList(
                        title=None,
                        contents=[
                            DescriptionParagraph(
                                contents=[DescriptionText(contents="item1")]
                            ),
                            DescriptionParagraph(
                                contents=[DescriptionText(contents="item2")]
                            ),
                        ],
                    ),
                ]
            ),
            DescriptionParagraph(contents=[DescriptionText(contents="more")]),
            DescriptionParagraph(
                contents=[
                    DescriptionList(
                        title=None,
                        contents=[
                            DescriptionParagraph(
                                contents=[DescriptionText(contents="item1")]
                            )
                        ],
                    )
                ]
            ),
        ]
    )
    assert desc == expected


def test_var_brief(doxygen):
    var = doxygen.collect("var_brief")
    desc = var.description

    print(desc)
    expected = DescriptionParagraph(
        contents=[DescriptionText(contents="brief description")]
    )
    assert desc == expected


def test_var_brief_and_detailed(doxygen):
    var = doxygen.collect("var_brief_and_detailed")
    desc = var.description

    print(desc)
    expected = DescriptionParagraph(
        contents=[
            DescriptionParagraph(
                contents=[DescriptionText(contents="brief description")]
            ),
            DescriptionParagraph(
                contents=[DescriptionText(contents="Followed by a longer description")]
            ),
        ]
    )
    assert desc == expected


def test_var_markups(doxygen):
    var = doxygen.collect("var_markups")
    desc = var.description

    print(desc)
    expected = DescriptionParagraph(
        contents=[
            DescriptionText(
                contents="Test markups like <b>bold</b> and <em>italics</em> work as expected."
            )
        ]
    )
    assert desc == expected
