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
from rich_argparse import RawDescriptionRichHelpFormatter, RichHelpFormatter, RawTextRichHelpFormatter

# %%-----------------------------------------------------------------------------
import sunspotter_load
import sunspotter_crop

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
        print(f"\n\n--- {name} command --- \n")
        subparser.prog = f"{PROG_NAME} {name}"
        subparser.print_help()

# %% [markdown]
#  example how to test argparse apps with pytest
# https://pythontest.com/testing-argparse-apps/
# %%-----------------------------------------------------------------------------


def valid_latitude(value):
    float_value = float(value)
    if float_value < -90.0 or float_value > 90.0:
        raise argparse.ArgumentTypeError(
            f"Latitude must be between -90 and 90. Got: {value}")
    return float_value


def valid_longitude(value):
    float_value = float(value)
    if float_value < -180.0 or float_value > 180.0:
        raise argparse.ArgumentTypeError(
            f"Longitude must be between -180 and 180. Got: {value}")
    return float_value


def parse_idselect(s):
    """
    Parse --idselect [1,3,5-12,20] into a list of integers.
    Supports:
      - single ints: 3
      - ranges: 5-12
      - comma-separated lists inside brackets
    """
    s = s.strip()

    # Remove optional surrounding brackets
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]

    result = []

    for part in s.split(","):
        part = part.strip()
        if "-" in part:
            start, end = map(int, part.split("-"))
            if start > end:
                raise argparse.ArgumentTypeError(f"Invalid range: {part}")
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))

    return result


# %%-----------------------------------------------------------------------------

# ===============================================================================
# Parser definition
# ===============================================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG_NAME,
        description="""SunSpotter: Processing images of the Sun from the Dwarf telescope\n\n

A utility for loading, processing, and analyzing FITS images of the Sun captured with the Dwarf telescope..

Use `sunspotter doc` to display the full documentation.
Or run `sunspotter CMD --help` for detailed information about a specific command.
""",
        epilog="""
\n\n
Notes:
- Defaults for all paths are relative to the data root, use / as directory separator
- Tested with files from Dwarf3 telescope, but should work with Dwarf2 as well

\nProudly handmade by Jarda Pulpan.\n
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

    parser.add_argument(
        "--idselect",
        type=parse_idselect,
        default=None,
        help="Select source file IDs, e.g. --idselect [1,3,5-12,20] (default=None)"
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

    # -------------------------------------------------------------------------------
    # crop command
    # -------------------------------------------------------------------------------
    p_process = subparsers.add_parser(
        "location",
        help="defines named location with LAT/LON in database table locations",
        description="""
Save named location into database table locations to be used for crop command.

- Format of Earth equatorial coordinates:
   Latitude (–90° to +90°, North positive) and 
   Longitude (–180° to +180°, East positive), 
   expressed as floating‑point values in decimal degrees.

        """,
        formatter_class=RawDescriptionRichHelpFormatter,
    )

    # Mutually exclusive: either --list OR (name+lat+lon)
    p_process.add_argument(
        "--list", 
        action="store_true",
        help="List all saved locations (default: False)"
    )

    # These are optional here, but validated later
    p_process.add_argument(  # "--name", help="Location name")
        # p_process.add_argument(
        "--loc",
        default=None,
        help="Name of the observation site to be saved into location table (required if not --list only)",
    )

    # p_loc.add_argument("--lat", type=float,
    #                    help="Latitude in decimal degrees")
    # p_loc.add_argument("--lon", type=float,
    #                    help="Longitude in decimal degrees")

    # p_process.add_argument(
    #     "--loc",
    #     required=True,
    #     help="Name of the observation site to be saved into location table (required)",
    # )

    p_process.add_argument(
        "--lat",
        type=valid_latitude,
        default=None,
        help="Latitude  (-90 to 90) of the observation site (required if LOC provided )",
    )

    p_process.add_argument(
        "--lon",
        type=valid_longitude,
        default=None,
        help="Longitude (-180 to 180) of the observation site (required if LOC provided )",
    )

    p_process.set_defaults(
        func=lambda args:
        sunspotter_crop.location(
            verbose=args.verbose,
            dbfilename=args.dbfilename,
            lat=args.lat,
            lon=args.lon,
            loc=args.loc,
            list=args.list
        )
    )

    # -------------------------------------------------------------------------------
    # crop command
    # -------------------------------------------------------------------------------
    p_process = subparsers.add_parser(
        "crop",
        help="Rotate and crop files from working directory to crop directory",
        description="""
Identify Sun in source images, rotate it by parallactic angle, crop image and save them to crop directory.

- Rotation is defined by parallactic angle, that is calculated from the observation location (parameters LAT/LON) and observation time (DATE_OBS in FITS header). 
- Observation location name could be defined by `sunspotter location` command that stores named location with LAT/LON in database table locations.
- Parameter ANGLE could be used to correct parallactic angle (or set parallactic angle if location is not provided).
- Format of Earth equatorial coordinates:
   Latitude (–90° to +90°, North positive) and 
   Longitude (–180° to +180°, East positive), 
   expressed as floating‑point values in decimal degrees.

- Images to be processes are selected by date range (global arguments DATE_FROM, DATE_TO) or by selecting set of source file IDs using global argument IDSELECT.
        """,
        formatter_class=RawDescriptionRichHelpFormatter,
    )
    p_process.add_argument(
        "--wrkdir",
        default=None,
        help="Working directory of files loaded from Dwarf source directory DWARF,(default: DATAROOT/source)"
    )
    p_process.add_argument(
        "--cropdir",
        default=None,
        help="Directory of cropped files (default: DATAROOT/crop)"
    )

    p_process.add_argument(
        "-a", "--angle",
        default=0,
        type=float,
        help="Correction of the parallactic angle computed from geographic longitude and latitude, or direct assignment of the parallactic angle when the observation site was not provided. (default: 0)",
    )

    p_process.add_argument(
        "--loc",
        default=None,
        help="Name of the observation site to be read from location table (default: none )",
    )

    p_process.add_argument(
        "--lat",
        type=valid_latitude,
        default=None,
        help="Latitude  (-90 to 90) of the observation site (default: None )",
    )

    p_process.add_argument(
        "--lon",
        type=valid_longitude,
        default=None,
        help="Longitude (-180 to 180) of the observation site (default: None )",
    )

    p_process.add_argument(
        "-s", "--size",
        default=400,
        type=int,
        help="Side length (in pixels) of the square cropped image (default: 400)",
    )

    p_process.set_defaults(
        func=lambda args:
        sunspotter_crop.crop(
            verbose=args.verbose,
            date_from=args.date_from,
            date_to=args.date_to,
            idselect=args.idselect,
            # ids=args.ids,
            dbfilename=args.dbfilename,
            wrkdir=args.wrkdir,
            cropdir=args.cropdir,
            angle=args.angle,
            size=args.size,
            lat=args.lat,
            lon=args.lon,
            loc=args.loc
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
                    value = expand_optional(
                        default_dir + '/' + default_suffix)
                else:
                    value = expand_optional(value)
                    # value = str(expand_optional(default_dir)) + default_suffix
                setattr(args, arg, value)
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
            set_default_arg(arg, value, "cropdir",
                            args.dataroot, "/crop ")
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


# test_sunspotter()
# %%-----------------------------------------------------------------------------
if __name__ == "__main__":
    raise SystemExit(main())
# %%-----------------------------------------------------------------------------
