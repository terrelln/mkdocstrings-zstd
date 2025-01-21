#!/usr/bin/env python3
# A script to invoke mkdocs with the correct environment.
# Additionally supports deploying via mike:
#   ./mkdocs deploy

import errno
import os
import shutil
import sys
from pathlib import Path
from subprocess import call

example_dir = Path(__file__).parent
root_dir = example_dir.parent
zstd_handler_dir = root_dir / "src"
config_path = os.path.join(example_dir, "mkdocs.yml")


build_dir = root_dir / "build-docs"

# Set PYTHONPATH for the mkdocstrings handler.
env = os.environ.copy()
path = env.get("PYTHONPATH")
env["PYTHONPATH"] = (path + ":" if path else "") + str(zstd_handler_dir)

# redirect_page = \
# '''<!DOCTYPE html>
# <html>
# <head>
#   <meta charset="utf-8">
#   <title>Redirecting</title>
#   <noscript>
#     <meta http-equiv="refresh" content="1; url=11.0/" />
#   </noscript>
#   <script>
#     window.location.replace(
#       "api/" + window.location.search + window.location.hash
#     );
#   </script>
# </head>
# <body>
#   Redirecting to <a href="api/">api</a>...
# </body>
# </html>
# '''

args = sys.argv[1:]
if len(args) > 0:
    command = args[0]
    if command == "deploy":
        git_url = "https://github.com/" if "CI" in os.environ else "git@github.com:"
        site_repo = git_url + "fmtlib/fmt.dev.git"

        site_dir = os.path.join(build_dir, "fmt.dev")
        try:
            shutil.rmtree(site_dir)
        except OSError as e:
            if e.errno == errno.ENOENT:
                pass
        ret = call(["git", "clone", "--depth=1", site_repo, site_dir])
        if ret != 0:
            sys.exit(ret)

        # Copy the config to the build dir because the site is built relative to it.
        config_build_path = os.path.join(build_dir, "mkdocs.yml")
        shutil.copyfile(config_path, config_build_path)

        version = args[1]
        ret = call(
            ["mike"]
            + args
            + ["--config-file", config_build_path, "--branch", "master"],
            cwd=site_dir,
            env=env,
        )
        if ret != 0 or version == "dev":
            sys.exit(ret)
        redirect_page_path = os.path.join(site_dir, version, "api.html")
        with open(redirect_page_path, "w") as file:
            file.write(redirect_page)
        ret = call(["git", "add", redirect_page_path], cwd=site_dir)
        if ret != 0:
            sys.exit(ret)
        ret = call(["git", "commit", "--amend", "--no-edit"], cwd=site_dir)
        sys.exit(ret)
    elif not command.startswith("-"):
        args += ["-f", config_path]
sys.exit(call(["mkdocs"] + args, env=env))
