# Healthcare Provider Lookup Project

### Description
This program creates a web page that allows users to search and filter through healthcare proivders in the US based on things like location, name, specialty etc...

### Disclaimer
The data file this program reads through is too large to include in Github

### How to Run

1. Clone this repository:
git clone https://github.com/KDastur/[your-repo-name].git
2. Navigate into the project folder:
cd [your-repo-name]
3. Install dependencies:
pip install -r requirements.txt
4. Download the NPPES NPI data files from CMS (not included in this repo due to file size):
   https://download.cms.gov/nppes/NPI_Files.html

   You need the **full replacement monthly NPI file**, which includes:
   - `npidata_pfile_[date].csv`
   - `pl_pfile_[date].csv`
   - `othername_pfile_[date].csv`

5. Place these three CSV files into a `Data/` folder in the project root

6. Open `build_db.py` and update the filenames at the top (`NPI_FILE`, `PL_FILE`, `OTHER_FILE`) to match the exact filenames you downloaded, since CMS includes the release date in each filename and it changes monthly

7. Build the database:
python build_db.py
   This generates `npi.db` in the project root (~3-5GB). Takes 10-30 minutes depending on hardware.

8. Run the app:
streamlit run Lookup-program.py

9. Streamlit will open the app in your browser automatically (usually at `http://localhost:8501`)
