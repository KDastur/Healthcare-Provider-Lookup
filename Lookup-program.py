"""
Kyle Dastur
6/29/2026
Search for healthcare providers using different filters and data
This code creates a website that allows users to interact and search for healthcare providers based on different filters
"""

import sqlite3
import os
import csv
import glob
import streamlit as st
import pandas as pd


# File paths used by the app
DB_PATH      = "npi.db"
TAXONOMY_CSV = "nucc_taxonomy.csv"

# Only real US state and territory abbreviations — used to clean up the state dropdown
VALID_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
    "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
    "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
    "TX","UT","VT","VA","WA","WV","WI","WY","DC","PR","GU","VI","AS","MP",
}


# Page layout and title
st.set_page_config(page_title="Healthcare Provider Finder", layout="wide")
st.markdown("""
# Healthcare Provider Finder
Locate healthcare providers across the United States using NPI data.
Search by name, organization, specialty, or location to quickly find relevant providers.
""")
st.divider()


# Reads the NUCC taxonomy CSV and builds a simple lookup from code to display name.
# For example: "207K00000X" becomes "Allergy & Immunology Physician"
# This runs once when the app starts, not on every page load.
def load_taxonomy_map():
    code_to_name = {}

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, TAXONOMY_CSV),
        os.path.join(os.getcwd(), TAXONOMY_CSV),
    ]
    candidates += glob.glob(os.path.join(script_dir, "**", TAXONOMY_CSV), recursive=True)
    candidates += glob.glob(os.path.join(os.getcwd(), "**", TAXONOMY_CSV), recursive=True)

    found = next((p for p in candidates if os.path.isfile(p)), None)
    if not found:
        return code_to_name

    with open(found, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = [h.strip() for h in next(reader)]
        try:
            code_idx    = headers.index("Code")
            display_idx = headers.index("Display Name")
        except ValueError:
            return code_to_name

        for row in reader:
            if len(row) <= max(code_idx, display_idx):
                continue
            code    = row[code_idx].strip()
            display = row[display_idx].strip()
            if code and display:
                code_to_name[code] = display

    return code_to_name


# Load the taxonomy map once at startup so it's available throughout the app
TAXONOMY_MAP = load_taxonomy_map()


# Opens a connection to the SQLite database.
# The connection is cached so it stays open across user interactions instead of reconnecting each time.
@st.cache_resource
def get_connection():
    if not os.path.exists(DB_PATH):
        st.error(
            f"Database '{DB_PATH}' not found. "
            "Please run build_db.py first to create it from the CSV files."
        )
        st.stop()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA cache_size=-500000")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


# Pulls the list of states from the database and filters out any junk values
# so the dropdown only shows real two-letter state codes like FL, TX, NY etc.
# The result is cached for one hour so it doesn't re-query on every interaction.
@st.cache_data(ttl=3600)
def get_distinct_states():
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT state FROM providers WHERE state != '' ORDER BY state"
    ).fetchall()
    valid = [r[0] for r in rows if r[0].upper() in VALID_STATES]
    return ["All"] + sorted(valid)


# Pulls all unique taxonomy codes from the database and converts them to
# human-readable specialty names using the NUCC taxonomy map.
# Returns a sorted list of (display name, code) pairs for the dropdown.
@st.cache_data(ttl=3600)
def get_taxonomy_options():
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT taxonomy_1 FROM providers WHERE taxonomy_1 != ''"
    ).fetchall()
    options = []
    for (code,) in rows:
        label = TAXONOMY_MAP.get(code, code)
        options.append((label, code))
    options.sort(key=lambda x: x[0].lower())
    return options


# Maximum number of results to return from any single search.
# Keeping this low ensures the app stays fast even on large queries.
MAX_RESULTS = 100


# Runs the provider search against the database using whatever filters are active.
# Builds the SQL query dynamically so that only the filters the user has set are applied.
# Each of the four search fields (first name, last name, org name, NPI) is applied
# independently so they can be combined freely — e.g. first + last narrows to a person,
# org alone finds organizations, NPI alone does an exact-style lookup.
def run_query(query_first, query_last, query_org, query_npi,
              entity_type, taxonomy_code, city, state,
              zip_code, address_type, active_only):
    conn = get_connection()

    conditions = []
    params = []

    # First name — matches against the first_name column (individuals only)
    if query_first:
        conditions.append("p.first_name LIKE ?")
        params.append(f"%{query_first}%")

    # Last name — matches against the last_name column (individuals only)
    if query_last:
        conditions.append("p.last_name LIKE ?")
        params.append(f"%{query_last}%")

    # Organization name — matches against org_name and the other_names join table
    if query_org:
        q = f"%{query_org}%"
        conditions.append("(p.org_name LIKE ? OR on2.other_name LIKE ?)")
        params.extend([q, q])

    # NPI — exact prefix match (user can type a partial NPI)
    if query_npi:
        conditions.append("p.npi LIKE ?")
        params.append(f"%{query_npi}%")

    # Filter by individual provider vs organization
    if entity_type == "Individual":
        conditions.append("p.entity_type = '1'")
    elif entity_type == "Organization":
        conditions.append("p.entity_type = '2'")

    # Filter by taxonomy code (specialty)
    if taxonomy_code and taxonomy_code != "ALL":
        conditions.append("(p.taxonomy_1 = ? OR p.taxonomy_2 = ?)")
        params.extend([taxonomy_code, taxonomy_code])

    # Location filters — applied to primary or secondary address depending on the address type selection
    if state != "All":
        col = "sl.state" if address_type == "Secondary" else "p.state"
        conditions.append(f"{col} = ?")
        params.append(state)
        
    if city:
        col = "sl.city" if address_type == "Secondary" else "p.city"
        conditions.append(f"{col} LIKE ?")
        params.append(f"%{city}%")

    if zip_code:
        col = "sl.zip" if address_type == "Secondary" else "p.zip"
        conditions.append(f"{col} LIKE ?")
        params.append(f"{zip_code}%")

    # When filtering by secondary address, only include providers who have one
    if address_type == "Secondary":
        conditions.append("sl.npi IS NOT NULL")

    # Active providers are those with no deactivation date on file
    if active_only:
        conditions.append("(p.deactivation_date IS NULL OR p.deactivation_date = '')")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Join to secondary locations table only when needed
    if address_type == "Secondary":
        sl_join   = "JOIN secondary_locations sl ON p.npi = sl.npi"
        addr_cols = "sl.address1, sl.city, sl.state, sl.zip, sl.phone"
    else:
        sl_join   = "LEFT JOIN secondary_locations sl ON p.npi = sl.npi"
        addr_cols = "p.address1, p.city, p.state, p.zip, p.phone"

    sql = f"""
        SELECT DISTINCT
            p.npi,
            CASE p.entity_type
                WHEN '1' THEN 'Individual'
                WHEN '2' THEN 'Organization'
                ELSE p.entity_type
            END AS type,
            CASE
                WHEN p.entity_type = '1' THEN
                    TRIM(COALESCE(p.name_prefix||' ','') || COALESCE(p.first_name||' ','') ||
                         COALESCE(p.middle_name||' ','') || COALESCE(p.last_name,'') ||
                         COALESCE(', '||p.credential,''))
                ELSE COALESCE(p.org_name, '')
            END AS name,
            p.taxonomy_1 AS taxonomy_code,
            {addr_cols},
            CASE WHEN (p.deactivation_date IS NULL OR p.deactivation_date = '')
                 THEN 'Active' ELSE 'Inactive'
            END AS status
        FROM providers p
        LEFT JOIN other_names on2 ON p.npi = on2.npi
        {sl_join}
        {where}
        LIMIT {MAX_RESULTS}
    """

    try:
        df = pd.read_sql_query(sql, conn, params=params)
    except Exception as e:
        st.error(f"Query error: {e}")
        return pd.DataFrame()

    # Replace taxonomy codes in the results table with human-readable specialty names
    df["taxonomy_code"] = df["taxonomy_code"].map(
        lambda c: TAXONOMY_MAP.get(c, c) if c else ""
    )
    df.columns = ["NPI", "Type", "Name", "Specialty", "Address", "City", "State", "ZIP", "Phone", "Status"]
    return df


# Sidebar filters
st.sidebar.header("Filters")

provider_type = st.sidebar.selectbox("Provider Type", ["All", "Individual", "Organization"])

taxonomy_options = get_taxonomy_options()
taxonomy_labels  = ["All"] + [label for label, _ in taxonomy_options]
taxonomy_codes   = ["ALL"]  + [code  for _, code  in taxonomy_options]
selected_label   = st.sidebar.selectbox("Specialty", taxonomy_labels)
selected_code    = taxonomy_codes[taxonomy_labels.index(selected_label)]

state_filter        = st.sidebar.selectbox("State", get_distinct_states())
city_filter         = st.sidebar.text_input("City")
zip_filter          = st.sidebar.text_input("ZIP Code")
address_type_filter = st.sidebar.selectbox("Address Type", ["All", "Primary", "Secondary"])
active_only         = st.sidebar.checkbox("Active providers only", value=True)


# Main search bar — four separate fields for precise targeting
st.header("Search")
col1, col2, col3, col4 = st.columns(4)
with col1:
    query_first = st.text_input("First Name", placeholder="e.g. John")
with col2:
    query_last = st.text_input("Last Name", placeholder="e.g. Smith")
with col3:
    query_org = st.text_input("Organization Name", placeholder="e.g. Mayo Clinic")
with col4:
    query_npi = st.text_input("NPI Number", placeholder="e.g. 1234567890")

st.caption(f"Results are capped at {MAX_RESULTS} rows. Add filters or narrow your search to see specific providers.")
search_clicked = st.button("Search", type="primary")


# Results section
st.header("Results")

# Only run a search if the user has actually set something, so the app doesn't
# try to load all 8 million providers when the page first opens
has_filters = any([
    query_first, query_last, query_org, query_npi,
    provider_type != "All", selected_code != "ALL",
    city_filter, state_filter != "All", zip_filter,
    address_type_filter != "All", active_only,
])

if search_clicked or has_filters:
    with st.spinner("Searching..."):
        results = run_query(
            query_first=query_first,
            query_last=query_last,
            query_org=query_org,
            query_npi=query_npi,
            entity_type=provider_type,
            taxonomy_code=selected_code,
            city=city_filter,
            state=state_filter,
            zip_code=zip_filter,
            address_type=address_type_filter,
            active_only=active_only,
        )

    if results.empty:
        st.info("No providers found. Try broadening your search or removing some filters.")
    else:
        hit_cap = len(results) == MAX_RESULTS
        st.caption(
            f"{'First ' if hit_cap else ''}{len(results):,} provider(s) found"
            + (" — refine your search to see more specific results." if hit_cap else ".")
        )
        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True,
            column_config={
                "NPI":       st.column_config.TextColumn("NPI",       width="small"),
                "Type":      st.column_config.TextColumn("Type",      width="small"),
                "Name":      st.column_config.TextColumn("Name",      width="medium"),
                "Specialty": st.column_config.TextColumn("Specialty", width="large"),
                "Address":   st.column_config.TextColumn("Address",   width="medium"),
                "City":      st.column_config.TextColumn("City",      width="small"),
                "State":     st.column_config.TextColumn("State",     width="small"),
                "ZIP":       st.column_config.TextColumn("ZIP",       width="small"),
                "Phone":     st.column_config.TextColumn("Phone",     width="small"),
                "Status":    st.column_config.TextColumn("Status",    width="small"),
            }
        )

        csv_data = results.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download results as CSV",
            data=csv_data,
            file_name="provider_results.csv",
            mime="text/csv",
        )
else:
    st.info("Enter a search term or select a filter above to find providers.")
