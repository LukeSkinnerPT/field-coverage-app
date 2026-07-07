import json
import base64
import io

import requests
import streamlit as st
from PIL import Image, ImageOps, ImageDraw
from streamlit_image_coordinates import streamlit_image_coordinates


# -----------------------------
# ROBOFLOW SETTINGS
# -----------------------------
WORKSPACE_NAME = "lukes-workspace-uyfur"
WORKFLOW_ID = "custom-workflow"


# -----------------------------
# STREAMLIT SETUP
# -----------------------------
st.set_page_config(
    page_title="Field Coverage Analyzer",
    layout="wide"
)

st.title("Field Coverage Analyzer")
st.write(
    "Upload a field image, click points around the playing surface, "
    "then run the Roboflow Workflow."
)


# -----------------------------
# API KEY
# -----------------------------
api_key = st.secrets.get("ROBOFLOW_API_KEY", "")

if not api_key:
    st.error("Missing ROBOFLOW_API_KEY. Add it in Streamlit Cloud secrets before running.")
    st.stop()


# -----------------------------
# SESSION STATE
# -----------------------------
if "polygon_points_display" not in st.session_state:
    st.session_state.polygon_points_display = []

if "last_uploaded_name" not in st.session_state:
    st.session_state.last_uploaded_name = None


# -----------------------------
# IMAGE UPLOAD
# -----------------------------
uploaded_file = st.file_uploader(
    "Upload a field image",
    type=["jpg", "jpeg",

