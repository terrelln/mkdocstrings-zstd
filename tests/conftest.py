from pathlib import Path

import os
from tempfile import mkdtemp
import pytest
import shutil

from mkdocstrings_handlers.zstd.doxygen import Doxygen

@pytest.fixture(name="doxygen")
def fixture_doxygen() -> Doxygen:
    """Return a Doxygen instance.

    Returns:
        A Dandler instance.
    """

    test_dir = Path(__file__).parent
    tmp_dir = test_dir / "build" / "tests"
    os.makedirs(tmp_dir, exist_ok=True)
    xml_output = mkdtemp(dir=str(tmp_dir))

    yield Doxygen(
        source_directory=(test_dir / "c"),
        xml_output=xml_output,
        sources=["file1.h", "file2.h", "dir/file3.h"],
        predefined=[],
    )

    shutil.rmtree(xml_output)