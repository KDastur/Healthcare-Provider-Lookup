"""
build_db.py  —  Run this ONCE to build npi.db from the raw CSV files.
Place this file next to your Data/ folder and run:
    python build_db.py

Estimated time: 10–30 minutes depending on hardware.
Output: npi.db  (~3–5 GB on disk)
"""

import sqlite3
import csv
import os
import time

DB_PATH = "npi.db"
DATA_DIR = "Data"

NPI_FILE      = os.path.join(DATA_DIR, "npidata_pfile_20050523-20260607.csv")
PL_FILE       = os.path.join(DATA_DIR, "pl_pfile_20050523-20260607.csv")
OTHER_FILE    = os.path.join(DATA_DIR, "othername_pfile_20050523-20260607.csv")

# Only pull columns we actually need from the giant npidata file (330 cols → ~20)
NPI_COLS = {
    "NPI": "npi",
    "Entity Type Code": "entity_type",
    "Provider Last Name (Legal Name)": "last_name",
    "Provider First Name": "first_name",
    "Provider Middle Name": "middle_name",
    "Provider Name Prefix Text": "name_prefix",
    "Provider Name Suffix Text": "name_suffix",
    "Provider Credential Text": "credential",
    "Provider Organization Name (Legal Business Name)": "org_name",
    "Provider Business Practice Location Address City Name": "city",
    "Provider Business Practice Location Address State Name": "state",
    "Provider Business Practice Location Address Postal Code": "zip",
    "Provider First Line Business Practice Location Address": "address1",
    "Provider Second Line Business Practice Location Address": "address2",
    "Provider Business Practice Location Address Telephone Number": "phone",
    "Healthcare Provider Taxonomy Code_1": "taxonomy_1",
    "Healthcare Provider Taxonomy Code_2": "taxonomy_2",
    "Provider Sex Code": "sex",
    "NPI Deactivation Date": "deactivation_date",
    "Provider Enumeration Date": "enumeration_date",
    "Last Update Date": "last_update",
}

def build_providers_table(conn):
    print("Creating providers table...")
    conn.execute("DROP TABLE IF EXISTS providers")
    conn.execute("""
        CREATE TABLE providers (
            npi TEXT PRIMARY KEY,
            entity_type TEXT,
            last_name TEXT,
            first_name TEXT,
            middle_name TEXT,
            name_prefix TEXT,
            name_suffix TEXT,
            credential TEXT,
            org_name TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            address1 TEXT,
            address2 TEXT,
            phone TEXT,
            taxonomy_1 TEXT,
            taxonomy_2 TEXT,
            sex TEXT,
            deactivation_date TEXT,
            enumeration_date TEXT,
            last_update TEXT
        )
    """)
    conn.commit()

    print(f"Reading {NPI_FILE} (this will take a while)...")
    t0 = time.time()
    batch = []
    BATCH_SIZE = 10_000

    with open(NPI_FILE, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        col_map = {csv_col: db_col for csv_col, db_col in NPI_COLS.items() if csv_col in reader.fieldnames}
        db_cols = list(NPI_COLS.values())
        placeholders = ",".join(["?"] * len(db_cols))
        insert_sql = f"INSERT OR IGNORE INTO providers ({','.join(db_cols)}) VALUES ({placeholders})"

        for i, row in enumerate(reader):
            record = [row.get(csv_col, "").strip() for csv_col in NPI_COLS.keys()]
            batch.append(record)

            if len(batch) >= BATCH_SIZE:
                conn.executemany(insert_sql, batch)
                conn.commit()
                batch.clear()
                if i % 500_000 == 0 and i > 0:
                    elapsed = time.time() - t0
                    print(f"  {i:,} rows processed in {elapsed:.0f}s...")

        if batch:
            conn.executemany(insert_sql, batch)
            conn.commit()

    print(f"  Done in {time.time()-t0:.0f}s")

def build_secondary_locations_table(conn):
    print(f"Reading {PL_FILE}...")
    conn.execute("DROP TABLE IF EXISTS secondary_locations")
    conn.execute("""
        CREATE TABLE secondary_locations (
            npi TEXT,
            address1 TEXT,
            address2 TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            phone TEXT
        )
    """)
    conn.commit()

    batch = []
    with open(PL_FILE, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            batch.append((
                row.get("NPI","").strip(),
                row.get("Provider Secondary Practice Location Address- Address Line 1","").strip(),
                row.get("Provider Secondary Practice Location Address-  Address Line 2","").strip(),
                row.get("Provider Secondary Practice Location Address - City Name","").strip(),
                row.get("Provider Secondary Practice Location Address - State Name","").strip(),
                row.get("Provider Secondary Practice Location Address - Postal Code","").strip(),
                row.get("Provider Secondary Practice Location Address - Telephone Number","").strip(),
            ))
            if len(batch) >= 10_000:
                conn.executemany("INSERT INTO secondary_locations VALUES (?,?,?,?,?,?,?)", batch)
                conn.commit()
                batch.clear()
    if batch:
        conn.executemany("INSERT INTO secondary_locations VALUES (?,?,?,?,?,?,?)", batch)
        conn.commit()
    print("  Done.")

def build_other_names_table(conn):
    print(f"Reading {OTHER_FILE}...")
    conn.execute("DROP TABLE IF EXISTS other_names")
    conn.execute("""
        CREATE TABLE other_names (
            npi TEXT,
            other_name TEXT,
            name_type_code TEXT
        )
    """)
    conn.commit()

    batch = []
    with open(OTHER_FILE, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            batch.append((
                row.get("NPI","").strip(),
                row.get("Provider Other Organization Name","").strip(),
                row.get("Provider Other Organization Name Type Code","").strip(),
            ))
            if len(batch) >= 10_000:
                conn.executemany("INSERT INTO other_names VALUES (?,?,?)", batch)
                conn.commit()
                batch.clear()
    if batch:
        conn.executemany("INSERT INTO other_names VALUES (?,?,?)", batch)
        conn.commit()
    print("  Done.")

def build_indexes(conn):
    print("Building indexes (speeds up searches dramatically)...")
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_npi ON providers(npi)",
        "CREATE INDEX IF NOT EXISTS idx_state ON providers(state)",
        "CREATE INDEX IF NOT EXISTS idx_city ON providers(city)",
        "CREATE INDEX IF NOT EXISTS idx_entity ON providers(entity_type)",
        "CREATE INDEX IF NOT EXISTS idx_taxonomy ON providers(taxonomy_1)",
        "CREATE INDEX IF NOT EXISTS idx_last_name ON providers(last_name)",
        "CREATE INDEX IF NOT EXISTS idx_org_name ON providers(org_name)",
        "CREATE INDEX IF NOT EXISTS idx_deactivation ON providers(deactivation_date)",
        "CREATE INDEX IF NOT EXISTS idx_sl_npi ON secondary_locations(npi)",
        "CREATE INDEX IF NOT EXISTS idx_on_npi ON other_names(npi)",
    ]
    for sql in indexes:
        conn.execute(sql)
    conn.commit()
    print("  Done.")

if __name__ == "__main__":
    print(f"Building {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-1000000")  # ~1 GB cache

    build_providers_table(conn)
    build_secondary_locations_table(conn)
    build_other_names_table(conn)
    build_indexes(conn)

    conn.close()
    print(f"\n✅ Done! {DB_PATH} is ready. You can now run the Streamlit app.")
