from typing import Any, Mapping, Optional
from mkdocs_autorefs.references import AutorefsHookInterface
from .doxygen import DoxygenObject
from subprocess import PIPE, STDOUT, CalledProcessError, Popen
from pathlib import Path


def _clang_format(
    code: str, root_directory: Path, line_length: int, based_on_style
) -> str:
    """Format code using clang-format.

    Parameters:
        code: The code to format.
        line_length: The maximum line length.

    Returns:
        The formatted code.
    """
    cmd = [
        "clang-format",
        "-assume-filename",
        "input.cpp",
        "--style",
        f"{{BasedOnStyle: {based_on_style}, ColumnLimit: {line_length}}}",
    ]
    process = Popen(
        cmd,
        cwd=root_directory,
        stdin=PIPE,
        stdout=PIPE,
        stderr=STDOUT,
    )
    stdout, _ = process.communicate(input=code.encode())
    if process.returncode != 0:
        raise CalledProcessError(process.returncode, cmd)
    return stdout.decode().strip()


def do_format(code: str, config: Mapping[str, Any]) -> str:
    return _clang_format(
        code,
        config["source_directory"],
        config["line_length"],
        config["clang_format_based_on_style"],
    )


class AutorefsHook(AutorefsHookInterface):
    """Autorefs hook.

    With this hook, we're able to add context to autorefs (cross-references),
    such as originating file path and line number, to improve error reporting.
    """

    def __init__(
        self, current_object: DoxygenObject, config: Mapping[str, Any]
    ) -> None:
        """Initialize the hook.

        Parameters:
            current_object: The object being rendered.
            config: The configuration dictionary.
        """
        self.current_object = current_object
        """The current object being rendered."""
        self.config = config
        """The configuration options."""

    def expand_identifier(self, identifier: str) -> str:
        """Expand an identifier.

        Parameters:
            identifier: The identifier to expand.

        Returns:
            The expanded identifier.
        """
        return identifier

    def get_context(self) -> AutorefsHookInterface.Context:
        """Get the context for the current object.

        Returns:
            The context.
        """
        role = self.current_object.role
        origin = self.current_object.qualified_name

        if self.current_object.location is not None:
            filepath = self.current_object.location.file
            lineno = self.current_object.locaion.line
        else:
            filepath = ""
            lineno = 0

        return AutorefsHookInterface.Context(
            domain="c",
            role=role,
            origin=origin,
            filepath=filepath,
            lineno=lineno,
        )
