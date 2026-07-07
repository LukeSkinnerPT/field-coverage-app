import json
import base64
import io

import requests
import streamlit as st
from PIL import Image, ImageOps
from streamlit_drawable_canvas import st_canvas


WORKSPACE_NAME = "lukes-workspace-uyfur"
WORKFLOW_ID = "custom-workflow"


st.set_page_config(page_title="Field Coverage Analyzer", layout="wide")

st.title("Field Coverage Analyzer")
st.write("Upload a field image, draw the playing surface, then run the Roboflow Workflow.")

api_key = st.secrets.get("ROBOFLOW_API_KEY", "")

if not api_key:
    st.error("Missing ROBOFLOW_API_KEY. Add it in Streamlit Cloud secrets before running.")
    st.stop()


uploaded_file = st.file_uploader(
    "Upload a field image",
    type=["jpg", "jpeg", "png", "webp"]
)

if uploaded_file:
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image).convert("RGB")

    original_width, original_height = image.size

    st.subheader("Uploaded image preview")
    st.image(image, caption="Uploaded field image", use_column_width=True)

    # Resize for drawing so the canvas reliably renders in Streamlit Cloud.
    max_canvas_width = 900
    max_canvas_height = 650

    width_scale = max_canvas_width / original_width
    height_scale = max_canvas_height / original_height
    scale = min(width_scale, height_scale, 1.0)

    display_width = int(original_width * scale)
    display_height = int(original_height * scale)

    display_image = image.resize((display_width, display_height))

    st.subheader("Draw the playing surface")
    st.write(
        "Draw a polygon around the inside edge of the playing surface. "
        "Double click to finish the polygon."
    )

    canvas_result = st_canvas(
        fill_color="rgba(255, 255, 255, 0.15)",
        stroke_width=3,
        stroke_color="#FFFFFF",
        background_image=display_image,
        update_streamlit=True,
        height=display_height,
        width=display_width,
        drawing_mode="polygon",
        key="playing_surface_canvas",
    )

    polygon = None

    if canvas_result.json_data is not None:
        objects = canvas_result.json_data.get("objects", [])

        if objects:
            obj = objects[-1]

            points = obj.get("points", [])
            left = obj.get("left", 0)
            top = obj.get("top", 0)
            scale_x = obj.get("scaleX", 1)
            scale_y = obj.get("scaleY", 1)

            polygon = [
                [
                    int((left + p["x"] * scale_x) / scale),
                    int((top + p["y"] * scale_y) / scale)
                ]
                for p in points
            ]

    if polygon:
        st.success(f"Playing surface polygon captured with {len(polygon)} points.")
        with st.expander("Show polygon coordinates"):
            st.code(json.dumps(polygon), language="json")
    else:
        st.warning("Draw a polygon around the playing surface before running.")

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


