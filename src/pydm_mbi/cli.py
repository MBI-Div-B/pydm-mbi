"""
Start PyDM or Qt Designer with the MBI environment (stylesheet and components path).

    pydm-mbi run [--light] [pydm arguments ...] display.ui
    pydm-mbi designer [--light] [file.ui ...]
    pydm-mbi env [--light]           # print the variables as shell exports

The dark theme is the default (laser labs); --light selects the light stylesheet.

In a conda environment with the pydm-mbi package, the variables are already set on activation,
so plain `pydm` and `designer` work as well.
"""

import os
import shlex
import shutil
import sys

from .paths import environment

KEYS = ("PYDM_STYLESHEET", "PYDM_STYLESHEET_INCLUDE_DEFAULT", "PYDM_DISPLAYS_PATH")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    command, rest = args[0], args[1:]
    theme = "light" if "--light" in rest else "dark"
    rest = [a for a in rest if a != "--light"]
    env = environment(theme)

    if command == "env":
        for key in KEYS:
            print(f"export {key}={shlex.quote(env[key])}")
        return 0
    if command in ("run", "designer"):
        program = "pydm" if command == "run" else "designer"
        executable = shutil.which(program)
        if executable is None:
            print(f"pydm-mbi: {program} not found", file=sys.stderr)
            return 1
        os.execve(executable, [program, *rest], env)
    print(f"pydm-mbi: unknown command {command!r}, see pydm-mbi --help", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
