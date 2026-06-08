# pyinstaller - -onefile sunspotter.py
# %%-----------------------------------------------------------------------------
from pathlib import Path, PurePath
from pathlib import Path
import argparse
# from datetime import datetime
import datetime
from email import parser
import os
import sys
from zipfile import Path
import sunspotter_load

from rich_argparse import RawDescriptionRichHelpFormatter, RichHelpFormatter, RawTextRichHelpFormatter
#
# from rich_argparse.contrib import ExtendedParagraphRichHelpFormatter
# %%-----------------------------------------------------------------------------
# source documentation
# https://help.dwarflab.com/en/docs/How-to-View-and-Obtain-the-Files-on-DWARF-3

# %%-----------------------------------------------------------------------------
PROG_NAME = "sunspotter"

RichHelpFormatter.styles["argparse.prog"] = "bold cyan"
# {
#     # for positional-arguments and --options (e.g "--help")
#     'argparse.args': 'cyan',
#     # for group names (e.g. "positional arguments")
#     'argparse.groups': 'dark_orange',
#     # for argument's help text (e.g. "show this help message and exit")
#     'argparse.help': 'default',
#     # for metavariables (e.g. "FILE" in "--file FILE")
#     'argparse.metavar': 'dark_cyan',
#     # for %(prog)s in the usage (e.g. "foo" in "Usage: foo [options]")
#     'argparse.prog': 'grey50',
#     # for highlights of back-tick quoted text (e.g. "`some text`")
#     'argparse.syntax': 'bold',
#     # for descriptions, epilog, and --version (e.g. "A program to foo")
#     'argparse.text': 'default',
#     # for %(default)s in the help (e.g. "Value" in "(default: Value)")
#     'argparse.default': 'italic',
# }
# %%-----------------------------------------------------------------------------


# ===============================================================================
# DOC Command implementation
# ===============================================================================


def cmd_doc(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    # Print help for all subcommands with correct program prefix
    print(f"\n-- Summary of {PROG_NAME} documentation --\n")

    # Main help
    parser.prog = PROG_NAME
    parser.print_help()

    subparsers_action = next(
        a for a in parser._actions
        if isinstance(a, argparse._SubParsersAction)
    )

    for name, subparser in subparsers_action.choices.items():
        if name == "doc":
            continue
        # print("\n" + "=" * 72)
        print(f"--- {name} command --- \n")
        subparser.prog = f"{PROG_NAME} {name}"
        subparser.print_help()

# %% [markdown]
#  example how to test argparse apps with pytest
# https://pythontest.com/testing-argparse-apps/
# ===============================================================================
# Parser definition
# ===============================================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG_NAME,
        description="""SunSpotter: Processing images of the Sun from the Dwarf telescope\n\n

A utility for loading, processing, and analyzing Dwarf solar imaging datasets.

Use `sunspotter doc` to print full documentation.
Or try `sunspotter CMD --help ` for detailed documentation about command CMD
""",
        epilog="""
\n\n
Notes:
- Defaults for all paths are relative to the data root
- Tested with files from Dwarf3 telescope, but should work with Dwarf2 as well

\nProudly written by hand of Jarda Pulpan.\n
""",
        # formatter_class=RichHelpFormatter,
        formatter_class=RawTextRichHelpFormatter
    )

    # Global options
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose mode (default: False)",
    )

    parser.add_argument(
        "--dataroot",
        default=None,
        help="Data root directory (default: ../data)"
    )

    parser.add_argument(
        "--dbdir",
        default=None,
        help="Database directory (default: DATAROOT/db)"
    )

    parser.add_argument(
        "--dbfilename",
        default=None,
        help="Database filename (default: DBDIR/sunspotter.db)"
    )

    parser.add_argument(
        '--date_from',
        default="1900-01-01",
        type=datetime.datetime.fromisoformat,
        help='Start of capture date range, use ISOformat: YYYY-MM-DD or YYYY-MM-DD:HH:mm:ss (default: 1900-01-01)'
    )

    parser.add_argument(
        '--date_to',
        default="2099-12-31",
        type=datetime.datetime.fromisoformat,
        help='End of capture date range, use ISOformat: YYYY-MM-DD or YYYY-MM-DD:HH:mm:ss (default: 2099-12-31)'
    )

    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        metavar="CMD",
    )
    # -------------------------------------------------------------------------------
    # doc command
    # -------------------------------------------------------------------------------
    p_doc = subparsers.add_parser(
        "doc",
        help="Show documentation for all commands",
        description="Show documentation for all commands",
    )
    p_doc.set_defaults(func=lambda args, p=parser: cmd_doc(p, args))

    # -------------------------------------------------------------------------------
    # load command
    # -------------------------------------------------------------------------------
    p_process = subparsers.add_parser(
        "load",
        help="Load files from Dwarf3 source directory into working directory",
        description="""
Load stacked images of Sun from Dwarf source directory into SunSpotter working
directory and creates database of loaded entries.

The source directory is expected to have structure specific to the Dwarf telescope
with subdirectories for each date of observation, containing the stacked images
and metadata files.

It optionally moves source files to a new location, but by default it just copies them.
        """,
        formatter_class=RawDescriptionRichHelpFormatter,
    )
    p_process.add_argument(
        "--dwarf",
        default=None,
        help="Dwarf source directory (default: DATAROOT/dwarf)"
    )
    p_process.add_argument(
        "--wrkdir",
        default=None,
        help="Working directory of files loaded from Dwarf source directory DWARF,(default: DATAROOT/source)"
    )
    p_process.add_argument(
        "-n", "--newdb",
        action="store_true",
        help="Create a new database (default: False)",
    )
    p_process.add_argument(
        "-b", "--backup",
        default=False,
        action="store_true",
        help="Copy Dwarf source files to WRKDIR directory and move them to BCKDIR (default: False)",
    )
    p_process.add_argument(
        "--bckdir",
        default=None,
        help="Backup directory of files loaded from Dwarf source directory DWARF, (default: DATAROOT/dwarf_bck)"
    )

    p_process.set_defaults(
        func=lambda args:
        sunspotter_load.load(
            verbose=args.verbose,
            date_from=args.date_from,
            date_to=args.date_to,
            dbfilename=args.dbfilename,
            create_new_db=args.newdb,
            dwarf=args.dwarf,
            wrkdir=args.wrkdir,
            backup=args.backup,
            bckdir=args.bckdir,
        )
    )
    return parser


# %%-----------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main(argv=None) -> int:

    def expand_optional(value):
        """
        Expand a path optionally relative to a base directory.
        - None stays None
        - absolute paths stay absolute
        - relative paths resolve relative to base (if provided)
        - otherwise relative to cwd()
        """
        if value is None:
            return os.getcwd()
        else:
            return os.path.normpath(os.path.join(os.getcwd(), value))


    def set_default_dirs(args):

        def set_default_arg(arg, value, arg_name, default_dir, default_suffix):
            if arg == arg_name:
                if value is None:
                    value = expand_optional(default_dir + '/' + default_suffix)
                else:
                    value = expand_optional(value)
                    # value = str(expand_optional(default_dir)) + default_suffix
                setattr(args, arg,value)
                if args.verbose:
                    print(f"->{arg} expanded to: {getattr(args, arg)}")

        if args.verbose:
            print("\nInput parameters:")
        for arg, value in vars(args).items():
            # print(f"  {arg}: {value}")

            if args.verbose:
                print(f"  {arg}: {value}")
            set_default_arg(arg, value, "dataroot",
                            "..", "data")
            set_default_arg(arg, value, "dbdir",
                            args.dataroot, "/db")
            set_default_arg(arg, value, "dbfilename",
                            args.dbdir, "/sunspotter.db")
            set_default_arg(arg, value, "wrkdir",
                            args.dataroot, "/source")
            set_default_arg(arg, value, "dwarf",
                            args.dataroot, "/dwarf ")
            set_default_arg(arg, value, "bckdir",
                            args.dataroot, "/dwarf_bck ")

    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        print("SunSpotter: Starting.")
        print("Verbose mode enabled")
        print(f"[current directory:{os.getcwd()}]")

    set_default_dirs(args)
    if args.verbose:
        print("\nExpanded parameters:")
        for arg, value in vars(args).items():
            print(f"  {arg}: {value}")

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    args.func(args)
    if args.verbose:
        print("SunSpotter: Done.")
    return 0


def test_sunspotter():
    # main([
    #      "--help"
    #       ])

    # main([
    #     "doc"
    # ])

    main([
        "-v",
        "load",  "-n", "--wrkdir", "../data/source",
        #  "--help"
    ])


test_sunspotter()
# %%-----------------------------------------------------------------------------
# if __name__ == "__main__":
#     raise SystemExit(main())
# %%-----------------------------------------------------------------------------
