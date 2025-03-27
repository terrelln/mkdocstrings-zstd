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


class TextParser:
    def __init__(
        self, doxygen: Optional["Doxygen"] = None, allowlist: Optional[Set[str]] = None
    ) -> None:
        self._doxygen = doxygen
        self._allowlist = allowlist
        self._parsers = {
            "bold": self._parse_bold,
            "emphasis": self._parse_emphasis,
            "computeroutput": self._parse_computeroutput,
            "programlisting": self._parse_programlisting,
            "verbatim": self._parse_verbatim,
            "codeline": self._parse_codeline,
            "highlight": self._parse_highlight,
            "ref": self._parse_ref,
            "sp": self._parse_sp,
        }

    def _parse(
        self,
        node: ElementTree.Element,
        tag: str,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> str:
        if node.tag != tag:
            raise Exception(f"Invalid node {node.tag} expected {tag}")

        out = ""

        if prefix is not None:
            out += prefix

        if node.text:
            out += node.text

        for child in list(node):
            out += self.parse(child)

        if suffix is not None:
            out += suffix

        if node.tail:
            out += node.tail

        return out

    def _parse_bold(self, node: ElementTree.Element) -> str:
        return self._parse(node, "bold", "<b>", "</b>")

    def _parse_emphasis(self, node: ElementTree.Element) -> str:
        return self._parse(node, "emphasis", "<em>", "</em>")

    def _parse_computeroutput(self, node: ElementTree.Element) -> str:
        return self._parse(node, "computeroutput", "<code>", "</code>")

    def _parse_verbatim(self, node: ElementTree.Element) -> str:
        return self._parse(
            node, "verbatim", '<pre><code class="language-cpp">', "</code></pre>"
        )

    def _parse_codeline(self, node: ElementTree.Element) -> str:
        return self._parse(node, "codeline", "", "")

    def _parse_highlight(self, node: ElementTree.Element) -> str:
        return self._parse(node, "highlight", "", "")

    def _parse_sp(self, node: ElementTree.Element) -> str:
        return self._parse(node, "sp", " ", "")

    def _parse_programlisting(self, node: ElementTree.Element) -> str:
        language = node.get("filename")
        if language is not None:
            assert language.startswith(".")
            language = language[1:]
        prefix = f"\n```{language or ''}\n"
        code_parser = self.with_allowlist({"codeline", "highlight", "sp", "ref"})
        return code_parser._parse(node, "programlisting", prefix, "```\n")

    def _parse_ref(self, node: ElementTree.Element) -> str:
        if len(list(node)) != 0:
            raise ValueError(
                f"Unexpected children in <ref> tag with refid={node.get('refid')}"
            )
        out = node.text
        if self._doxygen is not None:
            qualified_name = self._doxygen.find_qualified_name(node)
            out.replace("[", "\\[")
            out.replace("]", "\\]")
            out = f"[{out}][{qualified_name}]"

        if node.tail:
            out += node.tail

        return out

    def with_allowlist(self, allowlist: Set[str]) -> "TextParser":
        return TextParser(doxygen=self._doxygen, allowlist=allowlist)

    def parse(self, node: ElementTree.Element) -> str:
        out = ""
        if self._allowlist is not None and node.tag not in self._allowlist:
            raise ValueError(f"Illegal tag '{node.tag}' in Doxygen XML")
        if node.tag in self._parsers:
            out += self._parsers[node.tag](node)
        else:
            raise ValueError(f"Unexpected tag '{node.tag}' in Doxygen XML")
        return out


def parse_simple_text(node: ElementTree.Element) -> str:
    """
    Parses text from an arbitrary node that may only contain "ref" children.
    The references are ignored.
    """
    parser = TextParser(allowlist={"ref"})

    text = ""
    if node.text:
        text += node.text

    for child in list(node):
        text += parser.parse(child)

    if node.tail:
        text += node.tail

    return text.strip()


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
    return parse_simple_text(node)


def parse_type(node: Optional[ElementTree.Element]) -> Optional[Type]:
    if node is None:
        return None
    name = parse_simple_text(node)
    return normalize_type(name)


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


class DescriptionParser:
    def __init__(
        self, doxygen: "Doxygen", parameters: Optional[List[Parameter]] = None
    ) -> None:
        self._parameters = parameters
        self._text_parser = TextParser(doxygen=doxygen)

    def _parse_text(self, node: ElementTree.Element) -> DescriptionText:
        return DescriptionText(contents=self._text_parser.parse(node).strip())

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
            return self._parse_text(node)


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


def parse_initializer(node: ElementTree.Element) -> Optional[str]:
    initializer = node.find("initializer")
    if initializer is not None:
        return parse_simple_text(initializer)
    return None


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
            EXTRACT_ALL          = YES
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

    def _parse_description(
        self, node: ElementTree.Element, parameters: Optional[List[Parameter]] = None
    ) -> Description:
        nodes = node.findall("briefdescription/para") + node.findall(
            "detaileddescription/para"
        )

        if len(nodes) == 0:
            return None

        parser = DescriptionParser(self, parameters)
        return parser.parse_para(nodes)

    def _parse_function(self, node: ElementTree.Element) -> Function:
        parameters = parse_parameters(ObjectKind.FUNCTION, node)
        return Function(
            type=some(parse_type(node.find("type"))),
            name=some(parse_name(node.find("name"))),
            parameters=parameters,
            description=self._parse_description(node, parameters),
            location=some(parse_location(node)),
        )

    def _parse_define(self, node: ElementTree.Element) -> Define:
        return Define(
            name=some(parse_name(node.find("name"))),
            parameters=parse_parameters(ObjectKind.DEFINE, node),
            initializer=parse_initializer(node),
            description=self._parse_description(node, []),
            location=some(parse_location(node)),
        )

    def _parse_enum_values(self, node: ElementTree.Element) -> List[EnumValue]:
        values = []
        for v in node.findall("enumvalue"):
            values.append(
                EnumValue(
                    name=some(parse_name(v.find("name"))),
                    initializer=parse_initializer(v),
                    description=self._parse_description(v, []),
                )
            )
        return values

    def _parse_enum(self, node: ElementTree.Element) -> Enum:
        return Enum(
            name=some(parse_name(node.find("name"))),
            description=self._parse_description(node, []),
            location=some(parse_location(node)),
            values=self._parse_enum_values(node),
        )

    def _parse_variable(self, node: ElementTree.Element) -> Variable:
        name = some(parse_name(node.find("name")))
        return Variable(
            type=some(parse_type(node.find("type"))),
            name=name,
            qualified_name=parse_name(node.find("qualifiedname")) or name,
            initializer=parse_initializer(node),
            description=self._parse_description(node, []),
            location=some(parse_location(node)),
        )

    def _parse_member(self, node: ElementTree.Element) -> DoxygenObject:
        kind = node.get("kind")
        if kind == "function":
            return self._parse_function(node)
        elif kind == "define":
            return self._parse_define(node)
        elif kind == "enum":
            return self._parse_enum(node)
        elif kind == "variable":
            return self._parse_variable(node)
        else:
            raise ValueError(f"Unsupported kind '{kind}' in Doxygen XML")

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
            title = parse_simple_text(title)
        else:
            title = name

        members = []

        for compound in node.findall("innerclass"):
            refid = some(compound.get("refid"))
            inner = self._parse_compound(self._load_compound(refid))
            members.append(inner)

        for member in node.findall("sectiondef/memberdef"):
            members.append(self._parse_member(member))

        return Compound(
            type=parse_compound_type(node),
            name=name,
            title=title,
            members=members,
            description=self._parse_description(node, []),
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
        return self._parse_member(node)

    def collect(self, identifier: str) -> DoxygenObject:
        obj = self._collect_member(identifier)
        if obj is not None:
            return obj

        obj = self._collect_compound(identifier)
        if obj is not None:
            return obj

        raise ValueError(f"Unknown identifier '{identifier}'")

    def find_qualified_name(self, ref: ElementTree.Element) -> Name:
        assert ref.tag == "ref"

        refid = ref.get("refid")
        if refid is None:
            raise ValueError("Missing refid in Doxygen XML")
        kindref = ref.get("kindref")
        if kindref is None:
            raise ValueError("Missing kindref in Doxygen XML")

        nodes = self._index.findall(f".//{kindref}[@refid='{refid}']/name")
        if len(nodes) == 0:
            print(f"{kindref}[@refid='{refid}']/name")
            raise ValueError(f"Unknown {kindref} reference {refid} in Doxygen XML")

        name = nodes[0].text

        for node in nodes:
            if node.text != name:
                raise ValueError(
                    f"{kindref} {refid} has two names: '{name}' and '{node.text}'"
                )
            if len(list(node)) != 0:
                raise ValueError(
                    f"Unexpected children in {kindref} reference {refid} in Doxygen XML"
                )

        return name
