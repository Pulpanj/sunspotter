# %%-----------------------------------------------------------------------------

import sys
import shutil
import hashlib
from astropy.io import fits
import datetime
import duckdb
import pandas as pd
from pathlib import Path
# %%-----------------------------------------------------------------------------


class Verbose:
    verbose = False   # class-level global verbosity flag

    @classmethod
    def set_verbose(cls, value: bool):
        cls.verbose = value

    @classmethod
    def print(cls, msg, *args, karg=None, **kwargs):
        """
        Prints message only if:
        - karg is True, OR
        - karg is None and class verbose flag is True
        """
        should_print = karg if karg is not None else cls.verbose

        if should_print:
            if args or kwargs:
                msg = msg.format(*args, **kwargs)
            print(msg)


# %%-----------------------------------------------------------------------------

def ensure_dir_exists(path: str | Path, name: str) -> str:
    p = Path(path)
    if not p.exists():
        sys.exit(f"ERROR: {name} does not exist: {p}")
        # print(f"{name} does not exist: {p}")
        # raise SystemExit()
    if not p.is_dir():
        sys.exit(f"{name} is not a directory: {p}")
    return str(p).rstrip()


def ensure_file_exists(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"DBFILENAME does not exist: {p}, use --newdb to create a new database")
    if not p.is_file():
        sys.exit(f"Expected a file, got a directory: {p}")
    return p


def delete_file_if_exists(path, verbose=True):
    p = Path(path)
    if p.is_file():
        p.unlink()
        if verbose:
            Verbose.print(f"Deleted file: {p}")


def get_next_id(con, table, id_column):
    try:
        result = con.execute(
            f"SELECT max({id_column}) FROM {table}"
        ).fetchone()[0]
        return 1 if result is None else result + 1
    except duckdb.CatalogException:
        return 1


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_get(hdr, key, cast=None):
    if key not in hdr:
        return None
    val = hdr[key]
    if cast:
        try:
            return cast(val)
        except Exception:
            return None
    return val


def timestamp_from_dateobs(date_obs):
    try:
        return datetime.datetime.fromisoformat(date_obs.replace("Z", ""))
    except Exception:
        return datetime.datetime.now()


def create_duckdb(db_path: str | Path):
    p = Path(db_path)
    if not p.parent.exists():
        raise FileNotFoundError(f"Directory does not exist: {p.parent}")
    con = duckdb.connect(str(p))
    return con


def create_log_table(db_path, table="app_log"):
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(p))

    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id_log INTEGER,
            timestamp TIMESTAMP,
            level TEXT,
            module TEXT,
            message TEXT,
            details TEXT
        );
    """)
    con.close()


def append_log(db_path, level, module, message, details=None, table="app_log"):
    con = duckdb.connect(str(db_path))

    # get next id
    next_id = get_next_id(con, table, "id_log")
    ts = datetime.datetime.now()

    con.execute(
        f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?)",
        (next_id, ts, level, module, message, details)
    )

    con.close()


def list_duckdb_tables(db_path):
    con = duckdb.connect(db_path)
    tables = con.execute("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_schema, table_name;
    """).fetchall()
    con.close()
    return tables


# %%-----------------------------------------------------------------------------


# def get_next_id(con, table, id_column):
#     try:
#         result = con.execute(
#             f"SELECT max({id_column}) FROM {table}"
#         ).fetchone()[0]
#         return 1 if result is None else result + 1
#     except duckdb.CatalogException:
#         return 1

# %%-----------------------------------------------------------------------------


# %%-----------------------------------------------------------------------------


def insert_FITS_headers_from_filelist(db_path, wrkdir, files_list, header_table="FITS_headers"):
    con = duckdb.connect(str(db_path))

    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {header_table} (
            id_header INTEGER,
            id_file INTEGER,
            parameter_name TEXT,
            datetime_value TIMESTAMP,
            int_value BIGINT,
            float_value DOUBLE,
            string_value TEXT,
            comment TEXT
        );
    """)
    # con.close()

    # 1) Load next header ID
    next_header_id = get_next_id(con, header_table, "id_header")

    all_rows = []
    Verbose.print(
        f"Inserting FITS headers for {len(files_list)} files into table {header_table}...")
    # 4) Loop over files
    for id_file, filename in files_list:
        FITS_path = Path(wrkdir) / filename

        if not FITS_path.is_file():
            Verbose.print(f"WARNING: missing FITS file: {fits_path}")
            continue

        with fits.open(fits_path) as hdul:
            hdr = hdul[0].header

            for key, value, comment in hdr.cards:
                if key in ("COMMENT", "HISTORY", ""):
                    continue

                dt_val = None
                int_val = None
                float_val = None
                str_val = None

                if isinstance(value, int):
                    int_val = value
                elif isinstance(value, float):
                    float_val = value
                elif isinstance(value, datetime.datetime):
                    dt_val = value
                else:
                    str_val = str(value)

                all_rows.append((
                    next_header_id,
                    id_file,
                    key,
                    dt_val,
                    int_val,
                    float_val,
                    str_val,
                    comment
                ))

                next_header_id += 1

    # 5) Bulk insert
    # con = duckdb.connect(str(db_path))
    if all_rows:
        con.executemany(
            f"""
            INSERT INTO {header_table}
            (id_header, id_file, parameter_name, datetime_value,
             int_value, float_value, string_value, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            all_rows
        )
        print(
            f"Inserted {len(all_rows)} FITS header entries for {len(files_list)} files into table {header_table} to database {db_path}")

    con.close()


# %%-----------------------------------------------------------------------------


def scan_and_store_files(
    root_dir, pattern, db_path, wrkdir,
    bckdir,
    date_from=datetime.datetime(1900, 1, 1),
    date_to=datetime.datetime(2099, 12, 31),
    backup=False, table="stacked_files", header_table="fits_headers"
):

 
    wrkdir = Path(wrkdir)
    bckdir = Path(bckdir)

    con = duckdb.connect(str(db_path))

    # 1) Create table with new columns
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id_file INTEGER,
            filename TEXT,
            dirname TEXT,
            ori_filename TEXT,
            hash TEXT,
            exptime DOUBLE,
            date_obs TIMESTAMP,
            filter TEXT,
            bitpix INTEGER,
            naxis INTEGER,
            naxis1 INTEGER,
            naxis2 INTEGER,
            valid BOOLEAN
        );
    """)

    next_id = get_next_id(con, table, "id_file")
    id_file_min = next_id

    # Load existing hashes to skip duplicates
    try:
        existing_hashes = {
            row[0] for row in con.execute(f"SELECT hash FROM {table}").fetchall()
            if row[0] is not None
        }
    except duckdb.CatalogException:
        existing_hashes = set()

    rows = []
    files = []
    # moved_dirs = set()

    # 2) Loop over files matching pattern
    Verbose.print(f"Scanning for files matching pattern: {pattern}")


    # root_dir = r"D:\ajps\astro\sunspotter\data\dwarf"

    root = Path(root_dir)
    flist = list(root.rglob(pattern))
    Verbose.print(f"Found {len(flist)} files matching pattern")
    # if not flist:
    #     return

    # 3) Loop over files
    for path in flist:
        if not path.is_file():

            Verbose.print(f"WARNING: skipping non-file: {path}")
            continue

        # Always copy file to wrkdir
        wrkdir.mkdir(parents=True, exist_ok=True)

        # Compute hash
        try:
            h = file_hash(path)
        except Exception as e:
            Verbose.print(f"WARNING: cannot hash file {path}: {e}")
            h = None

        # Default metadata
        exptime = date_obs = filter_ = None
        # expstart = expend = None
        bitpix = naxis = naxis1 = naxis2 = None
        valid = False

        # Read FITS header
        try:
            with fits.open(path) as hdul:
                hdr = hdul[0].header

                exptime = safe_get(hdr, "EXPTIME", float)
                date_obs = safe_get(hdr, "DATE-OBS")
                filter_ = safe_get(hdr, "FILTER")
                # expstart = safe_get(hdr, "EXPSTART", float)
                # expend = safe_get(hdr, "EXPEND", float)
                bitpix = safe_get(hdr, "BITPIX", int)
                naxis = safe_get(hdr, "NAXIS", int)
                naxis1 = safe_get(hdr, "NAXIS1", int)
                naxis2 = safe_get(hdr, "NAXIS2", int)
                object = safe_get(hdr, "OBJECT", str)

                valid = True

        except Exception as e:
            Verbose.print(f"WARNING: invalid FITS file {path}: {e}")

        # Skip files not capturing Sun
        if object != "Sun":
            continue

        # Determine new filename based on timestamp
        ts = timestamp_from_dateobs(
            date_obs) if date_obs else datetime.datetime.now()
        ts_str = ts.strftime("%Y%m%d_%H%M%S")

        # Skip files outside date range
        if not (date_from <= ts < date_to):
            continue

        new_filename = f"Sun_stacked_{ts_str}.fits"

        try:
            shutil.copy2(path, wrkdir / new_filename)
        except Exception as e:
            Verbose.print(f"WARNING: cannot copy {path} to wrkdir: {e}")

        # Backup logic: move whole directory
        if backup:
            src_dir = path.parent
            # if src_dir not in moved_dirs:
            Verbose.print(f"Moving directory:{src_dir} to {bckdir}")
            try:
                bckdir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src_dir), str(bckdir))
                # moved_dirs.add(src_dir)
            except Exception as e:
                Verbose.print(
                    f"WARNING: cannot move directory {src_dir}: {e}")

        # Skip duplicates
        if h in existing_hashes:
            Verbose.print(f"SKIPPING duplicate file: {path}")
            continue

        # Store metadata row
        Verbose.print(
            f"STORING file {new_filename} as id_file={next_id} from observation at {date_obs} from {path.parent} as  ")
        rows.append((
            next_id,
            new_filename,     # filename
            str(path.parent),
            # path.name,
            path.name,        # ori_name
            h,
            date_obs,
            exptime,
            filter_,
            # expstart,
            # expend,
            bitpix,
            naxis,
            naxis1,
            naxis2,
            valid
        ))

        files.append((
            next_id,
            new_filename,     # filename
        ))
        # Increment ID for next file
        next_id += 1

    # Bulk insert
    if rows:
        Verbose.print(
            f"Inserting metadata for {len(rows)} files into {table}...")
        con.executemany(
            f"""
            INSERT INTO {table}
            (id_file, filename, dirname, ori_filename, hash,
             date_obs, exptime,  filter, 
             bitpix, naxis, naxis1, naxis2, valid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows
        )
        print(
            f"Inserted metadata for {len(rows)} files into {table} to database {db_path}")
        print(f"Inserted id_files: {id_file_min} to {next_id - 1}")
    con.close()

    insert_fits_headers_from_filelist(
        db_path, wrkdir, files, header_table=header_table)


# %%-----------------------------------------------------------------------------

# %%-----------------------------------------------------------------------------


def get_table_columns_pd(db_path, table_name):
    con = duckdb.connect(db_path)
    df = con.execute(f"PRAGMA table_info('{table_name}')").fetchdf()
    con.close()
    return df


def show_table(db_path, table_name="stacked_files", nobs=5):
    con = duckdb.connect(db_path)

    cols = get_table_columns_pd(db_path, table_name)

    dftable = con.execute(f"""
            SELECT *
            FROM {table_name}
        """).df()
    Verbose.print("\n\n")
    Verbose.print(f"Table: {table_name}")
    Verbose.print("-" * 40)
    Verbose.print(cols)
    # Verbose.print(dftable.info())
    Verbose.print(f"Table: {table_name} - last {nobs} rows")
    Verbose.print("-" * 60)
    Verbose.print(dftable.tail(nobs))
    con.close()
    return dftable

# %%-----------------------------------------------------------------------------
# LOAD command


def load(
    verbose=True,
    dbfilename="../data/db/sunspotter.db",
    date_from=datetime.datetime(1900, 1, 1),
    date_to=datetime.datetime(2099, 12, 31),
    dwarf="../data/dwarf",
    create_new_db=False,
    wrkdir="../data/source",
    backup=False,
    bckdir="../data/dwarf_bck",
):
    """Load exposures into working directory."""

    Verbose.set_verbose(verbose)
    # Implementation for loading exposures
    if verbose:
        Verbose.print(f"Loading exposures from dwarf data: {dwarf}")
        Verbose.print(f"into working directory: {wrkdir}")
        Verbose.print(f"using database {dbfilename}")
        Verbose.print(f"date range from {date_from} to {date_to}")

    wrkdir = ensure_dir_exists(wrkdir, "Working directory")
    dwarf = ensure_dir_exists(dwarf, "Dwarf data directory")

    if not create_new_db:
        dbfilename = ensure_file_exists(dbfilename)
        # duckdb.connect(str(dbfilename))
    else:
        delete_file_if_exists(dbfilename, verbose=verbose)
        Verbose.print(f"New database created: {dbfilename}")
    create_log_table(dbfilename)
    append_log(
        dbfilename,
        level="INFO",
        module="create_new_db",
        message="Created new database",
        details=f"filename={dbfilename}"
    )

    if backup:
        bckdir = ensure_dir_exists(bckdir, "Backup directory")

    Verbose.print(f"Scanning for files in: {dwarf}")
    append_log(
        dbfilename,
        level="INFO",
        module="scan_and_store_files",
        message="Started scanning directory",
        details=dwarf
    )

    scan_and_store_files(
        dwarf,  "stacked*.FITS", 
        dbfilename, wrkdir, bckdir,
        date_from=date_from,
        date_to=date_to,
        backup=backup, table="stacked_files", header_table="FITS_headers")
    show_table(dbfilename, table_name="stacked_files")
    show_table(dbfilename, table_name="FITS_headers")

# %%-----------------------------------------------------------------------------


# %%-----------------------------------------------------------------------------

def test_load():
    load(
        verbose=True,
        dbfilename="../data/db/sunspotter.db",
        date_from=datetime.datetime(2025, 4, 1),
        date_to=datetime.datetime(2025, 5, 1),
        dwarf="../data/dwarf",
        create_new_db=True,
        wrkdir="../data/source",
        backup=False,
        bckdir="../data/dwarf_bck",
    )


# test_load()

#%%-----------------------------------------------------------------------------

if __name__ == "__main__":
    test_load()
# %%-----------------------------------------------------------------------------

