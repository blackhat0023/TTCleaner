import streamlit as st
import pandas as pd
import datetime
import time
import re
import io
import nltk
nltk.download('words')
from collections import Counter
from threading import Lock
from joblib import Parallel, delayed

# Import your existing logic from your local files
from utils import translate_text, split_location, punctuation_only
from config import TRANSLATABLE_COLS, N_JOBS, COLS_TO_CHECK, CRITICAL_COLS

# --- PAGE SETUP ---
st.set_page_config(page_title="Data Cleaner Portal", layout="wide")
st.title("🚀 Blackhat Data Processor")
st.markdown("---")

# --- LOAD THE GOLD LIST ---
# In a web portal, we allow the user to upload their own Gold List
gold_file = st.sidebar.file_uploader("Upload Gold List (CSV)", type=["csv"])
if gold_file:
    gold_df = pd.read_csv(gold_file)
    CLEAN_COMPANY_LIST = gold_df.iloc[:, 0].dropna().astype(str).unique().tolist()
    CLEAN_COMPANY_LIST.sort(key=len, reverse=True)
else:
    st.sidebar.warning("Please upload a Gold List to start.")
    CLEAN_COMPANY_LIST = []

# --- CLEANING LOGIC ---
def gold_standard_cleaning(name, reference_list):
    name_str = str(name).strip()
    if not name_str: return "", None
    if re.search(r'\bEMS\b|\bE\.M\.S\.\b', name_str, re.IGNORECASE):
        return "Electro Medical Systems", "Electro Medical Systems"
    cleaned_input = re.sub(r'[^\w\s]+$', '', name_str).strip()
    for clean_name in reference_list:
        pattern = r'\b' + re.escape(clean_name) + r'\b'
        if re.search(pattern, cleaned_input, re.IGNORECASE):
            return clean_name, clean_name
    return name_str, None

# --- FILE UPLOAD ---
uploaded_files = st.file_uploader("Upload Excel Files to Process", type=["xlsx"], accept_multiple_files=True)

if uploaded_files and CLEAN_COMPANY_LIST:
    if st.button("Start Processing"):
        start_time = time.time()
        overall_stats = Counter()
        
        for uploaded_file in uploaded_files:
            st.subheader(f"Processing: {uploaded_file.name}")
            df = pd.read_excel(uploaded_file)
            
            # Progress Bar for UI
            progress_bar = st.progress(0)
            status_text = st.empty()

            # 1. Clean Critical Cols
            for col in CRITICAL_COLS:
                if col in df.columns:
                    df[col] = df[col].astype(str).replace(['nan', 'None', 'NaN'], '').str.strip()

            # 2. Translation (Simplified for Web Stability)
            for col in TRANSLATABLE_COLS:
                if col in df.columns:
                    status_text.text(f"Translating {col}...")
                    # Note: In a web app, n_jobs might need to be lower depending on server CPU
                    new_col = f"{col}_en"
                    df[new_col] = df[col].apply(lambda x: translate_text(str(x))[0])
                    progress_bar.progress(30)

            # 3. Apply Gold Matches
            status_text.text("Matching against Gold List...")
            if "Company Name_en" in df.columns:
                results = [gold_standard_cleaning(x, CLEAN_COMPANY_LIST) for x in df["Company Name_en"]]
                df["Company Name_en"] = [r[0] for r in results]
                overall_stats.update([r[1] for r in results if r[1] is not None])
            progress_bar.progress(60)

            # 4. Location Split
            status_text.text("Splitting Locations...")
            loc_results = [split_location(str(l)) for l in df["Location"].fillna("")]
            df["City"], df["State"], df["Country"] = zip(*loc_results)
            progress_bar.progress(90)

            # 5. Review Flagging
            def check_row_issues(row):
                cols_to_verify = [c for c in COLS_TO_CHECK if c.lower() != 'country']
                issues = [col for col in cols_to_verify if not str(row.get(col, '')).strip() or punctuation_only(str(row.get(col, '')))]
                return ", ".join(issues)
            df["needs_review"] = df.apply(check_row_issues, axis=1)
            df["Needs_Manual"] = df["needs_review"] != ""

            # --- EXPORT TO DOWNLOAD ---
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df[~df["Needs_Manual"]].to_excel(writer, sheet_name="Cleaned", index=False)
                df[df["Needs_Manual"]].to_excel(writer, sheet_name="Review", index=False)
            
            st.download_button(
                label=f"Download Processed {uploaded_file.name}",
                data=output.getvalue(),
                file_name=f"cleaned_{uploaded_file.name}",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            progress_bar.progress(100)
            status_text.text("Done!")

        # Final Summary
        duration = str(datetime.timedelta(seconds=int(time.time() - start_time)))
        st.success(f"All files processed in {duration}")
        st.write("### Match Summary", overall_stats)
