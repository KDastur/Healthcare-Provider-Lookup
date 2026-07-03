# Healthcare Provider Lookup Project

### Description
This program creates a web page that allows users to search and filter through healthcare proivders in the US based on things like location, name, specialty etc...

### Disclaimer
The data file this program reads through is too large to include in Github

## How to Run

1. Clone this repository: git clone https://github.com/KDastur/[Healthcare-Provider-Lookup].git
2. Navigate into the project folder: cd [Healthcare-Provider-Lookup]
3. Install dependencies: pip install -r requirements.txt
4. Download the NPPES NPI data files from CMS (these are not included in this repo due to file size):
   https://download.cms.gov/nppes/NPI_Files.html
5. Place the downloaded CSV files into a `Data/` folder in the project root
6. Build the database: python build_db.py
This generates `npi.db` in the project root. This file is large (~3GB) and may take a few minutes to build.
7. Run the app: streamlit run Lookup-program.py
8. Streamlit will automatically open the app in your browser (usually at `http://localhost:8501`)
