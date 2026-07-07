import json
import base64
import io

import requests
import streamlit as st
from PIL import Image, ImageOps, ImageDraw
from streamlit_image_coordinates import streamlit_image_coordinates


WORKSPACE_NAME = "lukes-workspace-uyfur"
WORKFLOW_ID = "custom-workflow"


st.set_page_config(page_title="Field Coverage Analyzer", layout="wide")

st.title("Field Coverage Analyzer")
st.write("Upload a field image, click points around the playing surface, then run the Roboflow Workflow.")

api_key = st.secrets.get("ROBOFLOW_API_KEY", "")

if not api_key:
    st.error("Missing ROBOFLOW_API_KEY. Add it in Streamlit Cloud secrets before running.")
    st.stop()


if "polygon_points_display" not in st.session_state:
    st.session_state.polygon_points_display = []

uploaded_file = st.file_uploader(
    "Upload a field image",
    type=["jpg", "jpeg", "png", "webp"]
)

if uploaded_file:
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image).convert("RGB")

    original_width, original_height = image.size

    max_display_width = 1000
    max_display_height = 650

    width_scale = max_display_width / original_width
    height_scale = max_display_height / original_height
    scale = min(width_scale, height_scale, 1.0)

    display_width = int(original_width * scale)
    display_height = int(original_height * scale)

    display_image = image.resize((display_width, display_height))

    # Draw current polygon preview on the display image.
    preview = display_image.copy()
    draw = ImageDraw.Draw(preview)

    points = st.session_state.polygon_points_display

    if len(points) >= 2:
        draw.line(points, fill="white", width=3)

    if len(points) >= 3:
        draw.line([points[-1], points[0]], fill="white", width=2)

    for idx, point in enumerate(points):
        x, y = point
        r = 5
        draw.ellipse((x - r, y - r, x + r, y + r), fill="white", outline="black")
        draw.text((x + 8, y - 8), str(idx + 1), fill="white")

    st.subheader("Define the playing surface")
    st.write(
        "Click points around the inside edge of the playing surface. "
        "Use more points for oval fields. The polygon closes automatically once you have at least 3 points."
    )

    col_a, col_b, col_c = st.columns([1, 1, 4])

    with col_a:
        if st.button("Undo last point"):
            if st.session_state.polygon_points_display:
                st.session_state.polygon_points_display.pop()
                st.rerun()

    with col_b:
        if st.button("Clear polygon"):
            st.session_state.polygon_points_display = []
            st.rerun()

    click = streamlit_image_coordinates(
        preview,
        key="playing_surface_click_image"
    )

    if click is not None:
        x = int(click["x"])
        y = int(click["y"])

        # Avoid adding the same point repeatedly on reruns.
        if not points or points[-1] != (x, y):
            st.session_state.polygon_points_display.append((x, y))
            st.rerun()

    points = st.session_state.polygon_points_display

    polygon = None

    if len(points) >= 3:
        polygon = [
            [
                int(x / scale),
                int(y / scale)
            ]
            for x, y in points
        ]

        st.success(f"Playing surface polygon captured with {len(polygon)} points.")

        with st.expander("Show polygon coordinates"):
            st.code(json.dumps(polygon), language="json")
    else:
        st.warning("Click at least 3 points around the playing surface before running.")

    run = st.button("Run field coverage analysis", disabled=polygon is None)

    if run and polygon:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        url = f"https://serverless.roboflow.com/infer/workflows/{WORKSPACE_NAME}/{WORKFLOW_ID}"

        payload = {
            "api_key": api_key,
            "inputs": {
                "image": {
                    "type": "base64",
                    "value": image_b64
                },
                "playing_surface_zone": polygon
            }
        }

        with st.spinner("Running Roboflow Workflow..."):
            response = requests.post(url, json=payload, timeout=60)

        if response.status_code != 200:
            st.error("Roboflow Workflow request failed.")
            st.code(response.text)
            st.stop()

        result = response.json()

        if isinstance(result, dict) and "outputs" in result:
            output = result["outputs"][0]
        elif isinstance(result, list):
            output = result[0]
        elif isinstance(result, dict):
            output = result
        else:
            st.error("Unexpected response format from Roboflow.")
            st.code(json.dumps(result, indent=2))
            st.stop()

        st.subheader("Coverage Results")

        if "coverage_results" in output:
            st.json(output["coverage_results"])

        if "coverage_csv" in output:
            st.download_button(
                label="Download CSV",
                data=output["coverage_csv"],
                file_name="field_coverage.csv",
                mime="text/csv"
            )

        if "output_image" in output:
            output_image = output["output_image"]

            if isinstance(output_image, dict):
                b64 = output_image.get("value") or output_image.get("base64") or output_image.get("data")
            else:
                b64 = output_image

            if b64:
                try:
                    image_bytes = base64.b64decode(b64)
                    st.image(image_bytes, caption="Field coverage output", use_column_width=True)
                except Exception:
                    st.warning("Output image was returned, but could not be decoded.")
                    st.code(str(output_image))
            else:
                st.warning("No output image was returned.")
        else:
            st.warning("No output_image field was returned.")
            st.code(json.dumps(output, indent=2))
else:
    st.info("Upload an image to begin.")
