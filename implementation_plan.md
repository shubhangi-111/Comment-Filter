# Implementation Plan: Data Scope, RANSAC Analysis, and CRS Assignment

## Goal Description
This plan addresses three interrelated tasks requested to finalize the benchmark scope and robustness:
1. Restrict the benchmark data pipeline to only process Lunar image pairs `p1` and `p3` from `C:\Users\ANEESH\Desktop\SIH\data\cropped`.
2. Analyze and explain why RANSAC rejects inliers for cross-modal orbital pairs like `p3` while succeeding on simpler pairs.
3. Fix the missing CRS issue by leveraging `rasterio` (similar to `check_crs.py`) to inject proper geospatial bounds and coordinate reference systems when converting raw `.npy` arrays into GeoTIFF format for AROSICS support.

## User Review Required
> [!IMPORTANT]
> Please review the explanation for **Task 2 (RANSAC Behavior)** below to ensure it answers your question. If it does, approve this plan so we can implement the code changes for Tasks 1 and 3.

---

### Task 2 Explanation: Why RANSAC fails to generate proper inliers for `p3`

**Why RANSAC struggles on `p3` (IIRS vs. WAC) compared to simpler pairs:**

1. **The Homography Assumption:** The standard `cv2.findHomography` with RANSAC assumes that the scene is perfectly planar (flat) or that the camera only rotated (no translation).
2. **Terrain Relief & Parallax (p3):** The `p3` pair consists of IIRS and WAC orbital images. Because the moon's surface has craters and elevation changes (terrain relief), and the sensors capture it from different orbital viewpoints, the displacement of pixels is **not uniform**. A single 3x3 homography matrix cannot mathematically map a 3D crater viewed from two different angles.
3. **What RANSAC Does:** RANSAC tries to find *one* global homography that fits the most points. Because the crater terrain warps locally, true positive matches (correctly identified keypoints) will geometrically deviate from the "best fit" flat plane. RANSAC treats these deviations as "outliers" and discards them.
4. **Contrast (p1 vs p3):** On simpler synthetic pairs (like the `pair_1` toy data), the images are perfectly planar, so RANSAC works flawlessly. For your actual `p1` dataset (NAC vs OHRC), the model originally failed before RANSAC even started due to zero contrast (0 keypoints). But for `p3`, deep learning models like EfficientLoFTR might find some raw matches, but RANSAC discards them because the true terrain cannot be flattened into a single homography matrix. 

**Solution:** For deep orbital imagery, relying solely on global RANSAC homography is insufficient; algorithms like AROSICS that use localized grid-based transformations (Polynomial or Thin Plate Splines) are necessary.

---

## Proposed Changes

### Configuration and Data Filtering
#### [MODIFY] [convert_data.py](file:///c:/Users/ANEESH/Desktop/SIH/convert_data.py)
- Refactor the script to exclusively process the `p1` and `p3` folders inside `data\cropped`.
- Delete any toy datasets (e.g., `reference1.png`) inside `data\pairs` to strictly limit the pipeline to our scope.

### CRS Injection using Rasterio
#### [MODIFY] [convert_data.py](file:///c:/Users/ANEESH/Desktop/SIH/convert_data.py)
- Switch the output format from `.png` to `.tif` (GeoTIFF) to support embedded spatial metadata.
- Import `rasterio` and read the `overlap_bounds.json` located in the `p1` and `p3` folders.
- Calculate the affine transform using the bounding box coordinates (`lon_min`, `lon_max`, `lat_min`, `lat_max`) and the array dimensions.
- Write the normalized 8-bit array to GeoTIFF using `rasterio.open(..., 'w')` with `crs="EPSG:4326"` (or a Lunar sphere definition) and the computed `transform`. 
- This will fulfill the AROSICS requirement for CRS and fix the `PROJ.db` projection errors.

#### [MODIFY] [default.yaml](file:///c:/Users/ANEESH/Desktop/SIH/basebenchmarking/configs/default.yaml)
- Ensure the `dataset.supported_formats` includes `tif` and `tiff` so the new files are picked up.

## Verification Plan

### Automated Tests
- `pytest tests/` to ensure the core dataset loader still correctly discovers `.tif` files.

### Manual Verification
- Verify that `data/pairs` contains exactly 4 files: `ref_p1.tif`, `tgt_p1.tif`, `ref_p3.tif`, and `tgt_p3.tif`.
- Use `check_crs.py` or `gdalinfo` on the generated `.tif` files to confirm the CRS and geographic bounds are correctly injected.
- Re-run the benchmark to confirm AROSICS can read the spatial metadata.
