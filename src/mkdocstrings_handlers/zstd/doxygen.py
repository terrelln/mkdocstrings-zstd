from dataclasses import dataclass
from enum import auto, StrEnum
from typing import List, Optional, ClassVar, Set
import xml.etree.ElementTree as ElementTree
import os
from pathlib import Path
from subprocess import PIPE, STDOUT, CalledProcessError, Popen


def some[T](value: Optional[T]) -> T:
    if value is None:
        raise ValueError("Expected value to be non-null")
    return value


Name = str
Type = str


class DescriptionKind(StrEnum):
    ADMONITION = auto()
    ATTRIBUTES = auto()
    PARAMETER = auto()
    PARAGRAPH = auto()
    LIST = auto()
    RETURN = auto()
    TEXT = auto()

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.value.upper()}"


@dataclass
class DescriptionText:
    kind: ClassVar[DescriptionKind] = DescriptionKind.TEXT
    contents: str


@dataclass
class DescriptionParagraph:
    kind: ClassVar[DescriptionKind] = DescriptionKind.PARAGRAPH
    contents: List["Description"]


@dataclass
class DescriptionAdmonition:
    kind: ClassVar[DescriptionKind] = DescriptionKind.ADMONITION
    style: str
    title: str
    contents: "Description"


class ParameterDirection(StrEnum):
    IN = auto()
    OUT = auto()
    INOUT = auto()

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.value.upper()}"


@dataclass
class DescriptionParameter:
    kind: ClassVar[DescriptionKind] = DescriptionKind.PARAMETER
    name: Name
    description: "Description"
    type: Optional[Type] = None
    direction: Optional[ParameterDirection] = None


@dataclass
class DescriptionList:
    kind: ClassVar[DescriptionKind] = DescriptionKind.LIST
    title: Optional[str]
    contents: List["Description"]


@dataclass
class DescriptionReturn:
    kind: ClassVar[DescriptionKind] = DescriptionKind.RETURN
    description: "Description"
    title: Optional[str] = None


Description = (
    DescriptionText
    | DescriptionAdmonition
    | DescriptionParameter
    | DescriptionParagraph
    | DescriptionList
    | DescriptionReturn
    | None
)


@dataclass
class Parameter:
    type: Optional[Type]
    name: Optional[Name]


class ObjectKind(StrEnum):
    COMPOUND = auto()
    DEFINE = auto()
    ENUM = auto()
    FUNCTION = auto()
    VARIABLE = auto()

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.value.upper()}"


@dataclass
class Location:
    file: str
    line: int
    column: int


@dataclass
class Function:
    kind: ClassVar[ObjectKind] = ObjectKind.FUNCTION
    type: Type
    name: Name
    parameters: List[Parameter]
    description: Description
    location: Location

    @property
    def qualified_name(self) -> Name:
        return self.name

    @property
    def role(self) -> str:
        return "func"


@dataclass
class Variable:
    kind: ClassVar[ObjectKind] = ObjectKind.VARIABLE
    type: Type
    name: Name
    qualified_name: Name
    initializer: Optional[str]
    description: Description
    location: Location

    @property
    def role(self) -> str:
        return "var"


@dataclass
class Define:
    kind: ClassVar[ObjectKind] = ObjectKind.DEFINE
    name: Name
    parameters: Optional[List[Parameter]]
    initializer: Optional[str]
    description: Description
    location: Location

    @property
    def qualified_name(self) -> Name:
        return self.name

    @property
    def role(self) -> str:
        return "macro"


@dataclass
class EnumValue:
    name: Name
    initializer: Optional[str]
    description: Description


@dataclass
class Enum:
    kind: ClassVar[ObjectKind] = ObjectKind.ENUM
    name: Name
    description: Description
    values: List[EnumValue]
    location: Location

    @property
    def qualified_name(self) -> Name:
        return self.name

    @property
    def role(self) -> str:
        return "enum"


class CompoundType(StrEnum):
    GROUP = auto()
    STRUCT = auto()
    UNION = auto()

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.value.upper()}"


@dataclass
class Compound:
    kind: ClassVar[ObjectKind] = ObjectKind.COMPOUND
    type: CompoundType
    name: Name
    title: Optional[str]
    members: List["DoxygenObject"]
    description: Description
    location: Optional[Location]

    @property
    def qualified_name(self) -> Name:
        return self.name

    @property
    def role(self) -> str:
        return str(self.type)


DoxygenObject = Function | Define | Enum | Variable | Compound


def normalize_type(type_: Type) -> Type:
    type_ = type_.replace("< ", "<").replace(" >", ">")
    return type_.replace(" &", "&").replace(" *", "*")


def is_admonition(kind: str) -> bool:
    return kind in {"note", "warning", "todo", "bug", "remark"}


def admonition_style(kind: str) -> str:
    return {
        "note": "note",
        "warning": "warning",
        # TODO: use a different style for TODOs
        "todo": "warning",
        "bug": "bug",
        "remark": "info",
    }[kind]


def admonition_title(kind: str) -> str:
    return {
        "note": "Note",
        "warning": "Warning",
        "todo": "TODO",
        "bug": "Bug",
        "remark": "Remark",
    }[kind]


def parse_name(node: Optional[ElementTree.Element]) -> Optional[Name]:
    if node is None:
        return None
    return node.text


def parse_type(node: Optional[ElementTree.Element]) -> Optional[Type]:
    if node is None:
        return None
    result = node.text if node.text else ""
    # TODO: Handle cross refs
    for ref in list(node):
        result += ref.text
        if ref.tail:
            result += ref.tail
    result += node.tail.strip()
    return normalize_type(result)


def parse_parameters(
    kind: ObjectKind, node: ElementTree.Element
) -> Optional[List[Parameter]]:
    name_tag = {
        ObjectKind.FUNCTION: "declname",
        ObjectKind.DEFINE: "defname",
    }[kind]

    nodes = node.findall("param")
    if kind == ObjectKind.DEFINE and len(nodes) == 0:
        # Differentiate between a define with no parameters and a define with
        # 0 parameters
        return None

    params = []
    for p in nodes:
        param = Parameter(
            type=parse_type(p.find("type")),
            name=parse_name(p.find(name_tag)),
        )
        if kind == ObjectKind.DEFINE and param.name is None:
            if len(nodes) == 1:
                # This means a macro with 0 parameters
                break
            raise ValueError("Define parameter must have name")
        if kind == ObjectKind.FUNCTION and param.type is None:
            raise ValueError("Function parameter must have type")
        params.append(param)
    return params


class TextNodeParser:
    def __init__(self, tag: str) -> None:
        self._tag = tag

    def prefix(self, node: ElementTree.Element) -> str:
        raise NotImplementedError()

    def suffix(self, node: ElementTree.Element) -> str:
        raise NotImplementedError()

    def handle(
        self, node: ElementTree.Element, allowlist: Optional[Set[str]] = None
    ) -> str:
        if node.tag != self._tag:
            raise Exception(f"Invalid node {node.tag} expected {self._tag}")

        out = ""

        out += self.prefix(node)

        if node.text:
            out += node.text

        out += parse_text(list(node), allowlist)

        out += self.suffix(node)

        if node.tail:
            out += node.tail

        return out


class SimpleTextNodeParser(TextNodeParser):
    def __init__(self, tag: str, prefix: str, suffix: str):
        super().__init__(tag)
        self._prefix = prefix
        self._suffix = suffix

    def prefix(self, node: ElementTree.Element) -> str:
        return self._prefix

    def suffix(self, node: ElementTree.Element) -> str:
        return self._suffix


class CodeBlockNodeParser(SimpleTextNodeParser):
    def __init__(self, tag: str):
        super().__init__(tag, '<pre><code class="language-cpp">', "</code></pre>")


class ProgramListingNodeParser(TextNodeParser):
    """
    Converts <programlisting> back into markdown.
    """

    def __init__(self):
        super().__init__(tag="programlisting")

    def prefix(self, node: ElementTree.Element) -> str:
        language = node.get("filename")
        if language is not None:
            assert language.startswith(".")
            language = language[1:]
        return f"\n```{language or ''}\n"

    def handle(
        self, node: ElementTree.Element, allowlist: Optional[Set[str]] = None
    ) -> str:
        if node.tag != self._tag:
            raise Exception(f"Invalid node {node.tag} expected {self._tag}")

        if node.text:
            raise ValueError("Unexpected text in <programlisting>")

        out = ""

        out += self.prefix(node)

        # TODO: Support cross-refs
        out += parse_text(list(node), {"codeline", "highlight", "sp", "ref"})

        out += self.suffix(node)

        if node.tail:
            out += node.tail

        return out

    def suffix(self, node: ElementTree.Element) -> str:
        return "```\n"


TAG_TO_PARSER = {
    "bold": SimpleTextNodeParser("bold", "<b>", "</b>"),
    "emphasis": SimpleTextNodeParser("emphasis", "<em>", "</em>"),
    "computeroutput": SimpleTextNodeParser("computeroutput", "<code>", "</code>"),
    # "para": SimpleTextNodeParser("para", '<p markdown="1">', "</p>"),
    # "itemizedlist": SimpleTextNodeParser("itemizedlist", '<ul markdown="1">', "</ul>"),
    # "listitem": SimpleTextNodeParser("listitem", '<li markdown="1">', "</li>"),
    "programlisting": ProgramListingNodeParser(),
    "verbatim": CodeBlockNodeParser("verbatim"),
    "codeline": SimpleTextNodeParser("codeline", "", ""),
    "highlight": SimpleTextNodeParser("highlight", "", ""),
    "ref": SimpleTextNodeParser("ref", "", ""),  # TODO: Handle cross-refs
    "sp": SimpleTextNodeParser("sp", " ", ""),
}


def parse_text(
    nodes: List[ElementTree.ElementTree], allowlist: Optional[Set[str]] = None
) -> str:
    out = ""
    for node in nodes:
        if allowlist is not None and node.tag not in allowlist:
            raise ValueError(f"Illegal tag '{node.tag}' in Doxygen XML")
        if node.tag in TAG_TO_PARSER:
            out += TAG_TO_PARSER[node.tag].handle(node, allowlist)
        else:
            raise ValueError(f"Unexpected tag '{node.tag}' in Doxygen XML")
    return out.strip()


class DescriptionParser:
    def __init__(self, parameters: Optional[List[Parameter]] = None) -> None:
        self._parameters = parameters

    def _parse_simple(self, node: ElementTree.Element) -> DescriptionText:
        return DescriptionText(contents=parse_text([node]).strip())

    def _parse_para(self, node: ElementTree.Element) -> DescriptionParagraph:
        contents = []

        def append(description: Description):
            """
            Append the new section & merge in to previous one if applicable.
            """
            if description.kind == DescriptionKind.TEXT:
                description.contents = description.contents.strip()
                if not description.contents:
                    return

            if len(contents) == 0:
                contents.append(description)
                return

            if (
                description.kind == DescriptionKind.TEXT
                and contents[-1].kind == DescriptionKind.TEXT
            ):
                contents[-1].contents += " "
                contents[-1].contents += description.contents
                return

            if (
                description.kind == DescriptionKind.LIST
                and contents[-1].kind == DescriptionKind.LIST
                and description.title is not None
                and contents[-1].title == description.title
            ):
                contents[-1].contents += description.contents
                return

            contents.append(description)

        assert node.tag == "para"

        if node.text:
            append(DescriptionText(contents=node.text))

        for child in list(node):
            append(self.parse(child))
            if contents[-1].kind != DescriptionKind.TEXT and child.tail:
                append(DescriptionText(contents=child.tail))

        if node.tail:
            append(DescriptionText(contents=node.tail))

        return DescriptionParagraph(contents=contents)

    def parse_para(self, nodes: List[ElementTree.Element]) -> DescriptionParagraph:
        paragraphs = []
        for node in nodes:
            paragraphs.append(self._parse_para(node))
        if len(paragraphs) == 1:
            return paragraphs[0]
        return DescriptionParagraph(contents=paragraphs)

    def _parse_list(self, node: ElementTree.Element) -> DescriptionList:
        assert node.tag == "itemizedlist"

        contents = []

        for child in list(node):
            if child.tag != "listitem":
                raise ValueError("Only <listitem> allowed in <itemizedlist>")
            contents.append(self.parse_para(child.findall("para")))

        return DescriptionList(title=None, contents=contents)

    def _parse_simplesect(self, node: ElementTree.Element) -> Description:
        if node.text:
            raise ValueError("Unexpected text in <simplesect>")

        kind = some(node.get("kind"))

        contents = self.parse_para(node.findall("para"))

        if kind == "return":
            return DescriptionReturn(title="Returns", description=contents)
        elif is_admonition(kind):
            return DescriptionAdmonition(
                style=admonition_style(kind),
                title=admonition_title(kind),
                contents=contents,
            )
        elif kind == "pre" or kind == "post":
            title = {"pre": "Preconditions", "post": "Postconditions"}[kind]
            return DescriptionList(title=title, contents=[contents])
        else:
            raise ValueError(f"Unexpected kind '{kind}' in Doxygen XML")

    def _get_param_type(self, name: Name) -> Optional[Type]:
        if self._parameters is None:
            return None
        for p in self._parameters:
            if p.name == name:
                return p.type
        return None

    def _parse_parameterlist(self, node: ElementTree.Element) -> DescriptionList:
        if node.text:
            raise ValueError("Unexpected text in <parameterlist>")

        params = []

        for node in node.findall("parameteritem"):
            names = node.findall("parameternamelist/parametername")
            if len(names) != 1:
                raise ValueError(f"Expected exactly one parameter name, got {names}")
            name = some(parse_name(names[0]))

            params.append(
                DescriptionParameter(
                    type=self._get_param_type(name),
                    name=name,
                    description=self.parse_para(
                        node.findall("parameterdescription/para")
                    ),
                    direction=parse_direction(names[0]),
                )
            )

        return DescriptionList(
            title="Parameters",
            contents=params,
        )

    def parse(self, node: ElementTree.Element) -> Description:
        if node.tag == "para":
            return self.parse_para()
        elif node.tag == "simplesect":
            return self._parse_simplesect(node)
        elif node.tag == "parameterlist":
            return self._parse_parameterlist(node)
        elif node.tag == "itemizedlist":
            return self._parse_list(node)
        else:
            return self._parse_simple(node)


def parse_description(
    node: ElementTree.Element, parameters: Optional[List[Parameter]] = None
) -> Description:
    nodes = node.findall("briefdescription/para") + node.findall(
        "detaileddescription/para"
    )

    if len(nodes) == 0:
        return None

    parser = DescriptionParser(parameters)
    return parser.parse_para(nodes)


def parse_direction(node: ElementTree.Element) -> Optional[ParameterDirection]:
    direction = node.get("direction")
    if direction is None:
        return None
    if direction == "in":
        return ParameterDirection.IN
    elif direction == "out":
        return ParameterDirection.OUT
    elif direction == "inout":
        return ParameterDirection.INOUT
    else:
        raise ValueError(f"Invalid direction '{direction}'")


def parse_location(node: ElementTree.Element) -> Optional[Location]:
    location = node.find("location")
    if location is None:
        return None
    return Location(
        file=some(location.get("file")),
        line=int(location.get("line")),
        column=int(location.get("column")),
    )


def parse_function(node: ElementTree.Element) -> Function:
    parameters = parse_parameters(ObjectKind.FUNCTION, node)
    return Function(
        type=some(parse_type(node.find("type"))),
        name=some(parse_name(node.find("name"))),
        parameters=parameters,
        description=parse_description(node, parameters),
        location=some(parse_location(node)),
    )


def parse_define(node: ElementTree.Element) -> Define:
    initializer = node.find("initializer")
    if initializer is not None:
        initializer = initializer.text
    return Define(
        name=some(parse_name(node.find("name"))),
        parameters=parse_parameters(ObjectKind.DEFINE, node),
        initializer=initializer,
        description=parse_description(node, []),
        location=some(parse_location(node)),
    )


def parse_initializer(node: ElementTree.Element) -> Optional[str]:
    initializer = node.find("initializer")
    if initializer is not None:
        return initializer.text
    return None


def parse_enum_values(node: ElementTree.Element) -> List[EnumValue]:
    values = []
    for v in node.findall("enumvalue"):
        values.append(
            EnumValue(
                name=some(parse_name(v.find("name"))),
                initializer=parse_initializer(v),
                description=parse_description(v, []),
            )
        )
    return values


def parse_enum(node: ElementTree.Element) -> Enum:
    return Enum(
        name=some(parse_name(node.find("name"))),
        description=parse_description(node, []),
        location=some(parse_location(node)),
        values=parse_enum_values(node),
    )


def parse_variable(node: ElementTree.Element) -> Variable:
    name = some(parse_name(node.find("name")))
    return Variable(
        type=some(parse_type(node.find("type"))),
        name=name,
        qualified_name=parse_name(node.find("qualifiedname")) or name,
        initializer=parse_initializer(node),
        description=parse_description(node, []),
        location=some(parse_location(node)),
    )


def parse_member(node: ElementTree.Element) -> DoxygenObject:
    kind = node.get("kind")
    if kind == "function":
        return parse_function(node)
    elif kind == "define":
        return parse_define(node)
    elif kind == "enum":
        return parse_enum(node)
    elif kind == "variable":
        return parse_variable(node)
    else:
        raise ValueError(f"Unsupported kind '{kind}' in Doxygen XML")


def parse_compound_type(node: ElementTree.Element) -> CompoundType:
    kind = node.get("kind")
    if kind == "struct":
        return CompoundType.STRUCT
    elif kind == "union":
        return CompoundType.UNION
    elif kind == "group":
        return CompoundType.GROUP
    else:
        raise ValueError(f"Unsupported compound type '{kind}' in Doxygen XML")


class Doxygen:
    def __init__(
        self,
        source_directory: Path,
        sources: List[Path],
        xml_output: Path,
        predefined: List[str],
    ) -> None:
        self._doxyxml_dir = os.path.abspath(xml_output)
        os.makedirs(self._doxyxml_dir, exist_ok=True)
        # Run doxygen.
        cmd = ["doxygen", "-"]
        p = Popen(cmd, cwd=source_directory, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
        out, _ = p.communicate(
            input=r"""
            PROJECT_NAME         = zstd
            GENERATE_XML         = YES
            GENERATE_LATEX       = NO
            GENERATE_HTML        = NO
            INCLUDE_PATH         = {0}
            INPUT                = {1}
            XML_OUTPUT           = {2}
            QUIET                = NO
            AUTOLINK_SUPPORT     = NO
            MACRO_EXPANSION      = YES
            SKIP_FUNCTION_MACROS = NO
            PREDEFINED           = {3}
            """.format(
                source_directory,
                " ".join(sources),
                self._doxyxml_dir,
                " ".join([f'"{p}"' for p in predefined]),
            ).encode("utf-8")
        )
        if p.returncode != 0:
            raise CalledProcessError(p.returncode, cmd)

        with open(os.path.join(self._doxyxml_dir, "index.xml")) as f:
            self._index = ElementTree.parse(f)

        self._compound_xml = {}

    def _load_compound(self, refid: str) -> ElementTree.Element:
        if refid in self._compound_xml:
            return self._compound_xml[refid]

        xml_path = os.path.join(self._doxyxml_dir, f"{refid}.xml")
        with open(xml_path) as f:
            self._compound_xml[refid] = ElementTree.parse(f)
        return self._compound_xml[refid]

    def _parse_compound(self, node: ElementTree.Element) -> Compound:
        node = some(node.find("compounddef"))
        name = some(parse_name(node.find("compoundname")))
        title = node.find("title")
        if title is not None:
            title = title.text
        else:
            title = name

        members = []

        for compound in node.findall("innerclass"):
            refid = some(compound.get("refid"))
            inner = self._parse_compound(self._load_compound(refid))
            members.append(inner)

        for member in node.findall("sectiondef/memberdef"):
            members.append(parse_member(member))

        return Compound(
            type=parse_compound_type(node),
            name=name,
            title=title,
            members=members,
            description=parse_description(node, []),
            location=parse_location(node),
        )

    def _collect_compound(self, name: str) -> Optional[Compound]:
        nodes = self._index.findall(f"compound/name[.='{name}']/..")
        if len(nodes) == 0:
            return None
        if len(nodes) > 1:
            raise ValueError(f"Ambiguous compound name '{name}' in Doxygen XML")
        node = nodes[0]
        refid = some(node.get("refid"))
        node = self._load_compound(refid)

        return self._parse_compound(node)

    def _load_member_node(self, name: str) -> Optional[ElementTree.Element]:
        if "::" in name:
            compound, name = name.split("::")
            nodes = self._index.findall(
                f"compound/name[.='{compound}']/../member/name[.='{name}']/.."
            )
        else:
            nodes = self._index.findall(f"compound/member/name[.='{name}']/..")

        if len(nodes) == 0:
            return None

        refid = some(nodes[0].get("refid"))
        pos = refid.rfind("_")
        if pos == -1:
            raise ValueError(f"Invalid refid '{refid}' in Doxygen XML")
        refid = refid[:pos]

        nodes = self._load_compound(refid).findall(
            f"compounddef/sectiondef/memberdef/name[.='{name}']/.."
        )
        assert len(nodes) > 0
        if len(nodes) > 1:
            raise ValueError(f"Ambiguous name '{name}' in Doxygen XML")

        return nodes[0]

    def _collect_member(self, name: str) -> Optional[DoxygenObject]:
        node = self._load_member_node(name)
        if node is None:
            return None
        return parse_member(node)

    def collect(self, identifier: str) -> DoxygenObject:
        obj = self._collect_member(identifier)
        if obj is not None:
            return obj

        obj = self._collect_compound(identifier)
        if obj is not None:
            return obj

        raise ValueError(f"Unknown identifier '{identifier}'")
