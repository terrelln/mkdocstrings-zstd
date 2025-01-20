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


def escape_html(s: str) -> str:
    return s.replace("<", "&lt;")


Name = str
Type = str


class DescriptionKind(StrEnum):
    ADMONITION = auto()
    ATTRIBUTES = auto()
    PARAMETERS = auto()
    LIST = auto()
    RETURN = auto()
    TEXT = auto()


@dataclass
class DescriptionText:
    kind: ClassVar[DescriptionKind] = DescriptionKind.TEXT
    contents: str


@dataclass
class DescriptionAdmonition:
    kind: ClassVar[DescriptionKind] = DescriptionKind.ADMONITION
    style: str
    title: str
    contents: str


class ParameterDirection(StrEnum):
    IN = auto()
    OUT = auto()
    INOUT = auto()


@dataclass
class DescriptionParameter:
    name: Name
    description: str
    type: Optional[Type] = None
    direction: Optional[ParameterDirection] = None


@dataclass
class DescriptionParameters:
    kind: ClassVar[DescriptionKind] = DescriptionKind.PARAMETERS
    parameters: List[DescriptionParameter]
    title: Optional[str] = None


@dataclass
class DescriptionAttribute:
    name: Name
    description: str
    type: Optional[Type] = None


@dataclass
class DescriptionAttributes:
    kind: ClassVar[DescriptionKind] = DescriptionKind.ATTRIBUTES
    attributes: List[DescriptionAttribute]
    title: Optional[str] = None


@dataclass
class DescriptionList:
    kind: ClassVar[DescriptionKind] = DescriptionKind.LIST
    title: str
    contents: List[str]


@dataclass
class DescriptionReturn:
    kind: ClassVar[DescriptionKind] = DescriptionKind.RETURN
    description: str
    title: Optional[str] = None


DescriptionSection = (
    DescriptionText
    | DescriptionAdmonition
    | DescriptionParameters
    | DescriptionAttributes
    | DescriptionList
    | DescriptionReturn
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
    description: List[DescriptionSection]
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
    description: List[DescriptionSection]
    location: Location

    @property
    def role(self) -> str:
        return "var"


@dataclass
class Define:
    kind: ClassVar[ObjectKind] = ObjectKind.DEFINE
    name: Name
    parameters: Optional[List[Parameter]]
    value: Optional[str]
    description: List[DescriptionSection]
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
    description: List[DescriptionSection]


@dataclass
class Enum:
    kind: ClassVar[ObjectKind] = ObjectKind.ENUM
    name: Name
    description: List[DescriptionSection]
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


@dataclass
class Compound:
    kind: ClassVar[ObjectKind] = ObjectKind.COMPOUND
    type: CompoundType
    name: Name
    title: Optional[str]
    members: List["DoxygenObject"]
    description: List[DescriptionSection]
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


def parse_parameters(kind: ObjectKind, node: ElementTree.Element) -> List[Parameter]:
    name_tag = {
        ObjectKind.FUNCTION: "declname",
        ObjectKind.DEFINE: "defname",
    }[kind]

    params = []
    for p in node.findall("param"):
        param = Parameter(
            type=parse_type(p.find("type")),
            name=parse_name(p.find(name_tag)),
        )
        if kind == ObjectKind.FUNCTION:
            assert param.type is not None
        if kind == ObjectKind.DEFINE:
            assert param.name is not None
        params.append(param)
    return params


class NodeParser:
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


class SimpleNodeParser(NodeParser):
    def __init__(self, tag: str, prefix: str, suffix: str):
        super().__init__(tag)
        self._prefix = prefix
        self._suffix = suffix

    def prefix(self, node: ElementTree.Element) -> str:
        return self._prefix

    def suffix(self, node: ElementTree.Element) -> str:
        return self._suffix


class CodeBlockNodeParser(SimpleNodeParser):
    def __init__(self, tag: str):
        super().__init__(tag, '<pre><code class="language-cpp">', "</code></pre>")


class ProgramListingNodeParser(NodeParser):
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
    "bold": SimpleNodeParser("bold", "<b>", "</b>"),
    "emphasis": SimpleNodeParser("emphasis", "<em>", "</em>"),
    "computeroutput": SimpleNodeParser("computeroutput", "<code>", "</code>"),
    "para": SimpleNodeParser("para", '<p markdown="1">', "</p>"),
    "programlisting": ProgramListingNodeParser(),
    "verbatim": CodeBlockNodeParser("verbatim"),
    "codeline": SimpleNodeParser("codeline", "", ""),
    "highlight": SimpleNodeParser("highlight", "", ""),
    "ref": SimpleNodeParser("ref", "", ""),  # TODO: Handle cross-refs
    "sp": SimpleNodeParser("sp", " ", ""),
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
    return out


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


def parse_description_parameters(
    nodes: List[ElementTree.Element],
    parameters: List[Parameter],
) -> DescriptionParameters:
    params = []

    def get_type(name: Name) -> Optional[Type]:
        for p in parameters:
            if p.name == name:
                return p.type
        return None

    for node in nodes:
        names = node.findall("parameternamelist/parametername")
        if len(names) != 1:
            raise ValueError(f"Expected exactly one parameter name, got {names}")
        name = some(parse_name(names[0]))

        params.append(
            DescriptionParameter(
                type=get_type(name),
                name=name,
                description=parse_text(node.find("parameterdescription")),
                direction=parse_direction(names[0]),
            )
        )

    return DescriptionParameters(parameters=params)


def get_description_sections(nodes: List[ElementTree.Element]):
    for node in nodes:
        for child in list(node):
            if child.tag == "para":
                if child.text or len(list(child)) == 0:
                    yield child
                else:
                    for n in list(child):
                        yield n
            else:
                yield child


def parse_description(
    node: ElementTree.Element, parameters: List[Parameter]
) -> List[DescriptionSection]:
    nodes = node.findall("briefdescription") + node.findall("detaileddescription")

    description = []

    def append_list(title: str, content: str):
        if (
            len(description) > 0
            and description[-1].kind == DescriptionKind.LIST
            and description[-1].title == title
        ):
            description[-1].contents.append(content)
        else:
            description.append(DescriptionList(title=title, contents=[content]))

    for n in get_description_sections(nodes):
        if n.tag == "simplesect":
            kind = some(n.get("kind"))
            if kind == "return":
                description.append(DescriptionReturn(description=parse_text(list(n))))
            elif is_admonition(kind):
                description.append(
                    DescriptionAdmonition(
                        style=admonition_style(kind),
                        title=admonition_title(kind),
                        contents=parse_text(list(n)),
                    )
                )
            elif kind == "pre" or kind == "post":
                contents = parse_text(list(n))
                title = {"pre": "Preconditions", "post": "Postconditions"}[kind]
                append_list(title, contents)
            else:
                raise ValueError(f"Unexpected kind '{kind}' in Doxygen XML")
            continue

        if n.tag == "parameterlist" and some(n.get("kind")) == "param":
            description.append(
                parse_description_parameters(n.findall("parameteritem"), parameters)
            )
            continue
        description.append(DescriptionText(contents=parse_text([n])))

    return description


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
    value = node.find("initializer")
    if value is not None:
        value = value.text
    return Define(
        name=some(parse_name(node.find("name"))),
        parameters=parse_parameters(ObjectKind.DEFINE, node),
        value=value,
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
        source_dir: Path,
        sources: List[Path],
        xml_output: Path,
        predefined: List[str],
    ) -> None:
        self._doxyxml_dir = os.path.abspath(xml_output)
        os.makedirs(self._doxyxml_dir, exist_ok=True)
        # Run doxygen.
        cmd = ["doxygen", "-"]
        p = Popen(cmd, cwd=source_dir, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
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
                source_dir,
                " ".join(sources),
                self._doxyxml_dir,
                " ".join([f'"{p}"' for p in predefined])
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
