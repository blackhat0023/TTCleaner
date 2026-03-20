import streamlit as st
import pandas as pd
import datetime
import time
import re
import io
import nltk
from collections import Counter

# Import your existing logic
from utils import translate_text, split_location, punctuation_only
from config import TRANSLATABLE_COLS, CRITICAL_COLS, COLS_TO_CHECK

# --- PERSISTENT NLTK LOADING ---
@st.cache_resource
def load_nltk():
    try:
        nltk.download('words', quiet=True)
    except Exception as e:
        st.error(f"NLTK Download failed: {e}")

load_nltk()

# --- CACHED FUNCTIONS ---
@st.cache_data(show_spinner=False)
def cached_translate(text):
    if not text or pd.isna(text) or str(text).strip() == "": 
        return ""
    # Using your existing utils.translate_text
    txt, _ = translate_text(str(text))
    return txt

@st.cache_data(show_spinner=False)
def cached_gold_cleaning(name, reference_tuple):
    name_str = str(name).strip()
    if not name_str: return "", None
    
    # Special Rule: EMS / E.M.S.
    if re.search(r'\bEMS\b|\bE\.M\.S\.\b', name_str, re.IGNORECASE):
        return "Electro Medical Systems", "Electro Medical Systems"
    
    # Punctuation stripping
    cleaned_input = re.sub(r'[^\w\s]+$', '', name_str).strip()
    
    for clean_name in reference_tuple:
        pattern = r'\b' + re.escape(clean_name) + r'\b'
        if re.search(pattern, cleaned_input, re.IGNORECASE):
            return clean_name, clean_name
            
    return name_str, None

# --- UI LAYOUT ---
st.set_page_config(page_title="TTLS Data Portal", layout="wide", page_icon="🧪")

# Sidebar Controls
st.sidebar.title("Settings & Maintenance")
if st.sidebar.button("Clear Cache / Reset Memory"):
    st.cache_data.clear()
    st.sidebar.success("Cache Cleared!")

st.sidebar.markdown("---")
gold_file = st.sidebar.file_uploader("1. Upload Gold List (CSV)", type=["csv"])

st.title("🧪 TTLS Lead Cleaning Portal")
st.info("Upload your Excel files below. The system will use cached results to speed up processing.")

uploaded_files = st.file_uploader("2. Upload Raw Excel Files", type=["xlsx"], accept_multiple_files=True)

if uploaded_files and gold_file:
    # Convert list to tuple so it can be hashed by the cache
    gold_df = pd.read_csv(gold_file)
    ref_list = tuple(gold_df.iloc[:, 0].dropna().astype(str).unique().tolist())
    
    if st.button("🚀 Start Processing"):
        overall_start = time.time()
        
        for uploaded_file in uploaded_files:
            file_start = time.time()
            st.markdown(f"### 📄 Processing: `{uploaded_file.name}`")
            
            # Load Data
            df = pd.read_excel(uploaded_file)
            
            # 1. Clean Critical Columns
            for col in CRITICAL_COLS:
                if col in df.columns:
                    df[col] = df[col].astype(str).replace(['nan', 'None', 'NaN'], '').str.strip()

            # 2. Translate with Cache
            for col in TRANSLATABLE_COLS:
                if col in df.columns:
                    with st.status(f"Translating {col}...", expanded=False) as status:
                        df[f"{col}_en"] = df[col].apply(cached_translate)
                        status.update(label=f"Finished translating {col}", state="complete")

            # 3. Match Gold List
            if "Company Name_en" in df.columns:
                with st.spinner("Applying Gold Standard logic..."):
                    results = [cached_gold_cleaning(x, ref_list) for x in df["Company Name_en"]]
                    df["Company Name_en"] = [r[0] for r in results]

            # 4. Final Review Flagging (Using your utils)
            def check_issues(row):
                issues = [col for col in [c for c in COLS_TO_CHECK if c.lower() != 'country'] 
                          if not str(row.get(col, '')).strip() or punctuation_only(str(row.get(col, '')))]
                return ", ".join(issues)
            
            df["needs_review"] = df.apply(check_issues, axis=1)
            df["Needs_Manual"] = df["needs_review"] != ""

            # --- EXPORT SECTION ---
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df[df["Needs_Manual"] == False].to_excel(writer, sheet_name="Cleaned", index=False)
                df[df["Needs_Manual"] == True].to_excel(writer, sheet_name="Review", index=False)
            
            st.success(f"Processed `{uploaded_file.name}` in {time.time() - file_start:.2f}s")
            st.download_button(
                label=f"📥 Download Cleaned {uploaded_file.name}",
                data=output.getvalue(),
                file_name=f"Cleaned_{uploaded_file.name}",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.markdown("---")

        st.balloons()
        st.write(f"**Total Execution Time:** {time.time() - overall_start:.2f} seconds")
