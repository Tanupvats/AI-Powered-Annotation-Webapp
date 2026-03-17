import mimetypes
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

import streamlit as st
import cv2
import numpy as np
from PIL import Image
import streamlit.components.v1 as components
import base64
import io
import os
import json
import random

st.set_page_config(page_title="AI Annotator Web APP", layout="wide")
st.title("AI Annotator Web APP")

try:
    build_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "build")
    cv_tool = components.declare_component("cv_tool", path=build_dir)
except Exception as e:
    st.error(f"Failed to load component. Did you run `npm run build`? Error: {e}")

# Session State Variables
if 'rot_ref' not in st.session_state: st.session_state.rot_ref = 0
if 'rot_tgt' not in st.session_state: st.session_state.rot_tgt = 0
if 'rot_inp' not in st.session_state: st.session_state.rot_inp = 0
if 'rot_ann' not in st.session_state: st.session_state.rot_ann = 0

if 'annotations' not in st.session_state: st.session_state.annotations = []
if 'categories' not in st.session_state: st.session_state.categories = {}
if 'ann_id' not in st.session_state: st.session_state.ann_id = 1
if 'cat_id' not in st.session_state: st.session_state.cat_id = 1


def generate_new_colors():
    r, g, b = random.randint(50, 255), random.randint(50, 255), random.randint(50, 255)
    return f"rgb({r}, {g}, {b})", f"rgba({r}, {g}, {b}, 0.3)"

if 'current_colors' not in st.session_state: 
    st.session_state.current_colors = generate_new_colors()

def load_and_resize(upload, max_dim=800):
    img = Image.open(upload).convert("RGB")
    if max(img.width, img.height) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img

def pil_to_b64(pil_img):
    buffered = io.BytesIO()
    pil_img.save(buffered, format="JPEG", quality=85) 
    return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"

def pil_to_cv2(pil_img):
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def cv2_to_pil(cv_img):
    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))

def create_padded_preview(pil_img, box_size=(400, 240)):
    img_copy = pil_img.copy()
    img_copy.thumbnail(box_size, Image.Resampling.LANCZOS)
    bg = Image.new("RGB", box_size, (38, 39, 48))
    offset_x = (box_size[0] - img_copy.width) // 2
    offset_y = (box_size[1] - img_copy.height) // 2
    bg.paste(img_copy, (offset_x, offset_y))
    return bg

tab1, tab2, tab3 = st.tabs(["Seamless Clone", "Inpainting", "Custom Annotation"])


with tab1:
    st.markdown("Upload images, fix orientation, and trace your object.")
    col_uploader_ref, col_uploader_tgt = st.columns(2)
    with col_uploader_ref:
        ref_file = st.file_uploader("1. Upload Reference Image", type=["jpg", "png", "jpeg"], key="ref")
    with col_uploader_tgt:
        tgt_file = st.file_uploader("2. Upload Target Image", type=["jpg", "png", "jpeg"], key="tgt")

    if ref_file and tgt_file:
        ref_pil_base = load_and_resize(ref_file)
        tgt_pil_base = load_and_resize(tgt_file)
        
        ref_pil = ref_pil_base.rotate(st.session_state.rot_ref, expand=True)
        tgt_pil = tgt_pil_base.rotate(st.session_state.rot_tgt, expand=True)
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            colA, colB = st.columns([0.7, 0.3])
            with colA: st.subheader("1. Lasso Object")
            with colB:
                if st.button("↻ Rotate 90°", key="btn_rot_ref", use_container_width=True):
                    st.session_state.rot_ref = (st.session_state.rot_ref - 90) % 360
                    st.rerun()
            st.caption("Left click to place points. **Right-click** to close the shape.")
            ref_data = cv_tool(imageUrl=pil_to_b64(ref_pil), toolMode="polygon", key="ref_canvas")
            
        with c2:
            colC, colD = st.columns([0.7, 0.3])
            with colC: st.subheader("2. Select Center")
            with colD:
                if st.button("↻ Rotate 90°", key="btn_rot_tgt", use_container_width=True):
                    st.session_state.rot_tgt = (st.session_state.rot_tgt - 90) % 360
                    st.rerun()
            st.caption("Click anywhere to drop the placement point.")
            tgt_data = cv_tool(imageUrl=pil_to_b64(tgt_pil), toolMode="point", key="tgt_canvas")

        control_container = st.container()
        with control_container:
            st.divider()
            st.markdown("### Object Adjustments")
            col_ctrl_1, _, _, _ = st.columns([0.25, 0.25, 0.25, 0.25])
            with col_ctrl_1:
                clone_scale = st.slider("Scale Object", 0.1, 3.0, 1.0, 0.05)
                
        with c3:
            st.subheader("3. Live Previews")
            if ref_data and "polygon" in ref_data:
                ref_cv = pil_to_cv2(ref_pil)
                h, w = ref_cv.shape[:2]
                pts = np.array([[p['x'], p['y']] for p in ref_data["polygon"]], np.int32)
                mask_preview = np.zeros((h, w), dtype=np.uint8)
                cv2.fillPoly(mask_preview, [pts], 255)
                mask_pil = cv2_to_pil(cv2.cvtColor(mask_preview, cv2.COLOR_GRAY2RGB))
                mask_padded = create_padded_preview(mask_pil)
                st.image(mask_padded, caption="1. Extracted Mask", use_container_width=True)
                
                if tgt_data and "point" in tgt_data:
                    y_idx, x_idx = np.where(mask_preview > 0)
                    if len(y_idx) > 0 and len(x_idx) > 0:
                        y_min, y_max, x_min, x_max = y_idx.min(), y_idx.max(), x_idx.min(), x_idx.max()
                        cropped_mask = mask_preview[y_min:y_max+1, x_min:x_max+1]
                        
                        new_w, new_h = max(1, int(cropped_mask.shape[1] * clone_scale)), max(1, int(cropped_mask.shape[0] * clone_scale))
                        scaled_mask = cv2.resize(cropped_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
                        
                        cx, cy = int(tgt_data["point"]["x"]), int(tgt_data["point"]["y"])
                        tgt_cv = pil_to_cv2(tgt_pil)
                        proj_cv = tgt_cv.copy()
                        
                        x1, y1 = max(0, cx - new_w // 2), max(0, cy - new_h // 2)
                        x2, y2 = min(tgt_cv.shape[1], cx - new_w // 2 + new_w), min(tgt_cv.shape[0], cy - new_h // 2 + new_h)
                        mx1, my1 = max(0, -(cx - new_w // 2)), max(0, -(cy - new_h // 2))
                        mx2, my2 = mx1 + (x2 - x1), my1 + (y2 - y1)

                        if x1 < x2 and y1 < y2:
                            mask_crop = scaled_mask[my1:my2, mx1:mx2]
                            roi = proj_cv[y1:y2, x1:x2]
                            mask_indices = mask_crop > 0
                            green_pixels = np.array([0, 255, 0], dtype=np.uint8)
                            roi[mask_indices] = (roi[mask_indices] * 0.5 + green_pixels * 0.5).astype(np.uint8)
                            proj_cv[y1:y2, x1:x2] = roi
                            
                        proj_pil = cv2_to_pil(proj_cv)
                        proj_padded = create_padded_preview(proj_pil)
                        st.image(proj_padded, caption=f"2. Projection (Scale: {clone_scale}x)", use_container_width=True)
                else:
                    st.info("Click a point on the Target Image to see the Live Projection overlay!")
            else:
                st.info("Right-click on the reference canvas to lock in your selection and generate the mask!")

        with control_container:
            if st.button("Process Seamless Clone", type="primary", use_container_width=True):
                if not ref_data or "polygon" not in ref_data: st.warning("Please draw and right-click to close a polygon!")
                elif not tgt_data or "point" not in tgt_data: st.warning("Please click a point on the target image!")
                else:
                    try:
                        with st.spinner("Cloning using OpenCV..."):
                            ref_cv = pil_to_cv2(ref_pil)
                            pts = np.array([[p['x'], p['y']] for p in ref_data["polygon"]], np.int32)
                            mask = np.zeros(ref_cv.shape[:2], dtype=np.uint8)
                            cv2.fillPoly(mask, [pts], 255)
                            
                            y_idx, x_idx = np.where(mask > 0)
                            y_min, y_max, x_min, x_max = y_idx.min(), y_idx.max(), x_idx.min(), x_idx.max()
                            
                            cropped_ref = ref_cv[y_min:y_max+1, x_min:x_max+1]
                            cropped_mask = mask[y_min:y_max+1, x_min:x_max+1]
                            
                            new_w, new_h = max(1, int(cropped_ref.shape[1] * clone_scale)), max(1, int(cropped_ref.shape[0] * clone_scale))
                            scaled_ref = cv2.resize(cropped_ref, (new_w, new_h), interpolation=cv2.INTER_AREA)
                            scaled_mask = cv2.resize(cropped_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
                            
                            center = (int(tgt_data["point"]["x"]), int(tgt_data["point"]["y"]))
                            tgt_cv = pil_to_cv2(tgt_pil)
                            
                            result = cv2.seamlessClone(scaled_ref, tgt_cv, scaled_mask, center, cv2.NORMAL_CLONE)
                            
                            st.success("Seamless Clone Successful!")
                            res_pil = cv2_to_pil(result)
                            st.image(res_pil, caption="Final Result", use_column_width=True)
                            buf = io.BytesIO()
                            res_pil.save(buf, format="PNG")
                            st.download_button("Download Cloned Image", data=buf.getvalue(), file_name="clone.png", mime="image/png")
                    except Exception as e:
                        st.error(f"Error: {e}")


with tab2:
    st.markdown("Upload image, fix orientation, and paint over defects.")
    inp_file = st.file_uploader("Upload Image to Inpaint", type=["jpg", "png", "jpeg"], key="inp")
    
    if inp_file:
        inp_pil_base = load_and_resize(inp_file)
        inp_pil = inp_pil_base.rotate(st.session_state.rot_inp, expand=True)
        
        c1, c2 = st.columns(2)
        
        with c1:
            colA, colB = st.columns([0.7, 0.3])
            with colA: st.subheader("1. Draw Mask")
            with colB:
                if st.button("↻ Rotate 90°", key="btn_rot_inp", use_container_width=True):
                    st.session_state.rot_inp = (st.session_state.rot_inp - 90) % 360
                    st.rerun()
            st.caption("Paint over the object you want to remove. **Right-click** to generate the mask.")
            col_b1, col_b2 = st.columns([0.4, 0.6])
            with col_b1:
                brush = st.slider("Brush Size", 5, 50, 20)
                
            inp_data = cv_tool(imageUrl=pil_to_b64(inp_pil), toolMode="brush", brushSize=brush, key="inp_canvas")
            
        with c2:
            st.subheader("2. Live Mask Preview")
            if inp_data and "brushMask" in inp_data:
                encoded_data = inp_data["brushMask"].split(',')[1]
                nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
                img_mask = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
                
                if len(img_mask.shape) == 3 and img_mask.shape[2] == 4:
                    mask_cv = img_mask[:, :, 3] 
                else:
                    mask_cv = cv2.cvtColor(img_mask, cv2.COLOR_BGR2GRAY)
                
                _, mask_cv = cv2.threshold(mask_cv, 10, 255, cv2.THRESH_BINARY)
                mask_pil = cv2_to_pil(cv2.cvtColor(mask_cv, cv2.COLOR_GRAY2RGB))
                mask_padded = create_padded_preview(mask_pil)
                st.image(mask_padded, caption="Extracted Binary Mask", use_container_width=True)
                st.session_state.current_inp_mask = mask_cv
            else:
                st.info("Draw on the image and **Right-Click** the canvas to lock in your strokes and generate the mask!")
                st.session_state.current_inp_mask = None
        
        st.divider()
        if st.button("Process Inpainting", type="primary", use_container_width=True):
            if st.session_state.get('current_inp_mask') is None:
                st.warning("Please draw your strokes and Right-Click to generate the mask first!")
            else:
                with st.spinner("Restoring image..."):
                    inp_cv = pil_to_cv2(inp_pil)
                    mask_cv = st.session_state.current_inp_mask
                    mask_cv = cv2.resize(mask_cv, (inp_cv.shape[1], inp_cv.shape[0]), interpolation=cv2.INTER_NEAREST)
                    result = cv2.inpaint(inp_cv, mask_cv, 3, cv2.INPAINT_TELEA)
                    st.success("Inpainting Successful!")
                    res_pil = cv2_to_pil(result)
                    st.image(res_pil, caption="Restored Image", use_column_width=True)
                    buf = io.BytesIO()
                    res_pil.save(buf, format="PNG")
                    st.download_button("Download Inpainted Image", data=buf.getvalue(), file_name="inpaint.png", mime="image/png")


with tab3:
    st.markdown("Create a multi-class dataset. Draw shapes, assign classes, and download as COCO JSON.")
    ann_file = st.file_uploader("Upload Image to Annotate", type=["jpg", "png", "jpeg"], key="ann_file")

    if ann_file:
        ann_pil_base = load_and_resize(ann_file)
        ann_pil = ann_pil_base.rotate(st.session_state.rot_ann, expand=True)
        img_width, img_height = ann_pil.size
        
        c1, c2 = st.columns([0.6, 0.4])
        
        with c1:
            colA, colB, colC = st.columns([0.4, 0.4, 0.2])
            with colA: st.subheader("1. Workspace")
            with colB:
                ui_tool = st.radio("Tool Selection:", ["Square (BBox)", "Polygon"], horizontal=True, label_visibility="collapsed")
                active_tool = "rect" if ui_tool == "Square (BBox)" else "polygon"
            with colC:
                if st.button("↻ Rotate", key="btn_rot_ann", use_container_width=True):
                    st.session_state.rot_ann = (st.session_state.rot_ann - 90) % 360
                    st.rerun()
            
            st.caption(f"Drag to draw a {ui_tool}. **Right-Click** when finished to lock it in.")
            
            solid_c, trans_c = st.session_state.current_colors
            ann_data = cv_tool(
                imageUrl=pil_to_b64(ann_pil), 
                toolMode=active_tool, 
                solidColor=solid_c,       
                transColor=trans_c,       
                resetCounter=st.session_state.ann_id, 
                key="ann_canvas"
            )
            
        with c2:
            st.subheader("2. Save Annotation")
            class_name = st.text_input("Enter Class Name (e.g., car, pedestrian, dog):").strip().lower()
            
            if st.button("✅ Done (Save Annotation)", type="primary", use_container_width=True):
                if not class_name:
                    st.warning("Please enter a class name!")
                elif not ann_data or (active_tool == "rect" and "rect" not in ann_data) or (active_tool == "polygon" and "polygon" not in ann_data):
                    st.warning("Please draw a shape and **Right-Click** the canvas first!")
                else:
                    if class_name not in st.session_state.categories:
                        st.session_state.categories[class_name] = st.session_state.cat_id
                        st.session_state.cat_id += 1
                        
                    cat_id = st.session_state.categories[class_name]
                    
                    new_ann = {
                        "id": st.session_state.ann_id,
                        "class_name": class_name,
                        "category_id": cat_id
                    }
                    
                    if active_tool == "rect":
                        r = ann_data["rect"]
                        new_ann["bbox"] = [r['x'], r['y'], r['w'], r['h']]
                        new_ann["area"] = r['w'] * r['h']
                    elif active_tool == "polygon":
                        poly_pts = [[p['x'], p['y']] for p in ann_data["polygon"]]
                        flat_poly = [coord for pt in poly_pts for coord in pt]
                        pts_array = np.array(poly_pts, np.int32)
                        x, y, w, h = cv2.boundingRect(pts_array)
                        
                        new_ann["segmentation"] = [flat_poly]
                        new_ann["bbox"] = [float(x), float(y), float(w), float(h)]
                        new_ann["area"] = float(cv2.contourArea(pts_array))
                        
                    st.session_state.annotations.append(new_ann)
                    st.session_state.current_colors = generate_new_colors() 
                    st.session_state.ann_id += 1 
                    st.rerun()
                    
            if st.button("Clear All Annotations", use_container_width=True):
                st.session_state.annotations = []
                st.rerun()

        st.divider()
        st.subheader("3. Current Image Annotations")
        
        c3, c4 = st.columns([0.5, 0.5])
        
        with c3:
            
            preview_cv = pil_to_cv2(ann_pil)
            overlay = preview_cv.copy() 
            
            
            for ann in st.session_state.annotations:
                color_val = hash(ann["class_name"]) % 255
                bgr_color = (max(50, color_val), max(50, 255 - color_val), 150)
                
                if "segmentation" in ann:
                    pts = np.array(ann["segmentation"][0], np.int32).reshape((-1, 1, 2))
                    cv2.fillPoly(overlay, [pts], bgr_color)
                elif "bbox" in ann:
                    x, y, w, h = map(int, ann["bbox"])
                    cv2.rectangle(overlay, (x, y), (x+w, y+h), bgr_color, -1) 
            
            
            cv2.addWeighted(overlay, 0.4, preview_cv, 0.6, 0, preview_cv)
            
            
            for ann in st.session_state.annotations:
                color_val = hash(ann["class_name"]) % 255
                bgr_color = (max(50, color_val), max(50, 255 - color_val), 150)
                
                if "segmentation" in ann:
                    pts = np.array(ann["segmentation"][0], np.int32).reshape((-1, 1, 2))
                    cv2.polylines(preview_cv, [pts], isClosed=True, color=bgr_color, thickness=2)
                    cv2.putText(preview_cv, ann["class_name"], (pts[0][0][0], max(0, pts[0][0][1]-5)), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, bgr_color, 2)
                elif "bbox" in ann:
                    x, y, w, h = map(int, ann["bbox"])
                    cv2.rectangle(preview_cv, (x, y), (x+w, y+h), bgr_color, 2)
                    cv2.putText(preview_cv, ann["class_name"], (x, max(0, y-5)), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, bgr_color, 2)
            
            st.image(cv2_to_pil(preview_cv), caption="Annotated Image Preview", use_column_width=True)

        with c4:
            if len(st.session_state.annotations) > 0:
                st.dataframe([{"ID": a["id"], "Class": a["class_name"], "Type": "Polygon" if "segmentation" in a else "BBox"} for a in st.session_state.annotations], use_container_width=True)
                
                coco_format = {
                    "images": [{"id": 1, "width": img_width, "height": img_height, "file_name": ann_file.name}],
                    "categories": [{"id": v, "name": k} for k, v in st.session_state.categories.items()],
                    "annotations": []
                }
                for a in st.session_state.annotations:
                    coco_ann = {
                        "id": a["id"],
                        "image_id": 1,
                        "category_id": a["category_id"],
                        "iscrowd": 0,
                        "area": a["area"],
                        "bbox": a["bbox"]
                    }
                    if "segmentation" in a:
                        coco_ann["segmentation"] = a["segmentation"]
                    coco_format["annotations"].append(coco_ann)

                json_str = json.dumps(coco_format, indent=4)
                
                st.download_button(
                    label="⬇️ Download COCO JSON",
                    data=json_str,
                    file_name=f"{ann_file.name.split('.')[0]}_coco.json",
                    mime="application/json",
                    type="primary",
                    use_container_width=True
                )
            else:
                st.info("Your saved annotations and COCO export will appear here.")