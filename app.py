import json
import base64
import tempfile

import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from inference_sdk import InferenceHTTPClient


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
    image = Image.open(uploaded_file).convert("RGB")
    width, height = image.size

    max_display_width = 1000

    if width > max_display_width:
        scale = max_display_width / width
        display_width = int(width * scale)
        display_height = int(height * scale)
        display_image = image.resize((display_width, display_height))
    else:
        scale = 1.0
        display_width = width
        display_height = height
        display_image = image

    st.subheader("Draw the playing surface")
    st.write("Use the polygon tool to trace the inside edge of the playing surface. Double click to finish the polygon.")

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

            # Convert display canvas coordinates back to original image coordinates.
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
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            image.save(tmp.name)
            image_path = tmp.name

        client = InferenceHTTPClient(
            api_url="https://serverless.roboflow.com",
            api_key=api_key
        )

        with st.spinner("Running Roboflow Workflow..."):
            result = client.run_workflow(
                workspace_name=WORKSPACE_NAME,
                workflow_id=WORKFLOW_ID,
                images={
                    "image": image_path
                },
                parameters={
                    "playing_surface_zone": polygon
                },
                use_cache=False
            )

        output = result[0]

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
                image_bytes = base64.b64decode(b64)
                st.image(image_bytes, caption="Field coverage output", use_container_width=True)
            else:
                st.warning("No output image was returned.")
else:
    st.info("Upload an image to begin.")
