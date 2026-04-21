import os
from datetime import datetime
import streamlit as st

st.set_page_config(page_title="SURI", layout="wide")

st.title("SURI — Data Agent PoC")
st.caption(f"Deployed {datetime.now().isoformat(timespec='seconds')} · Railway Singapore")

col1, col2, col3 = st.columns(3)
col1.metric("Sprint Day", "D-9")
col2.metric("Deadline", "2026-04-29 14:59 KST")
col3.metric("Region", "asia-southeast1")

st.success("배포 성공 ✅ — Railway에서 앱이 살아있음")

with st.expander("Env sanity check"):
    st.write({
        "PORT": os.getenv("PORT"),
        "RAILWAY_ENV": os.getenv("RAILWAY_ENVIRONMENT"),
    })
