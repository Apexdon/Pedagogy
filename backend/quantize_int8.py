"""
INT8 Quantization Script for YOLO UI Detection Model

Uses Ultralytics built-in INT8 export with NNCF backend.
Calibration images from INT_screenshots folder.
"""

import os
import sys
from pathlib import Path
import yaml
import shutil

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def create_calibration_dataset(calibration_dir: Path, output_dir: Path):
    """
    Create a YOLO-format calibration dataset from raw images.
    """
    # Create directory structure
    images_dir = output_dir / "images" / "train"
    labels_dir = output_dir / "labels" / "train"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    # Copy images
    cal_images = list(calibration_dir.glob("*.png")) + list(calibration_dir.glob("*.jpg"))
    for img in cal_images:
        dest = images_dir / img.name
        if not dest.exists():
            shutil.copy(img, dest)
        # Create empty label file (just for calibration, no actual labels needed)
        label_file = labels_dir / (img.stem + ".txt")
        if not label_file.exists():
            label_file.touch()

    # Create dataset YAML
    dataset_yaml = {
        "path": str(output_dir.absolute()),
        "train": "images/train",
        "val": "images/train",  # Use same for val
        "nc": 1,  # Number of classes (placeholder)
        "names": ["ui_element"],  # Class name (placeholder)
    }

    yaml_path = output_dir / "calibration.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(dataset_yaml, f)

    print(f"Created calibration dataset with {len(cal_images)} images")
    return yaml_path


def main():
    from ultralytics import YOLO
    import time

    # Paths
    model_path = Path("weights/icon_detect/model.pt")
    calibration_dir = Path("INT_screenshots")
    calibration_dataset_dir = Path("calibration_dataset")

    # Verify paths
    if not model_path.exists():
        print(f"ERROR: Model not found at {model_path}")
        return 1

    if not calibration_dir.exists():
        print(f"ERROR: Calibration directory not found at {calibration_dir}")
        return 1

    # Count calibration images
    cal_images = list(calibration_dir.glob("*.png")) + list(calibration_dir.glob("*.jpg"))
    print(f"Found {len(cal_images)} calibration images in {calibration_dir}")

    if len(cal_images) < 10:
        print("WARNING: Fewer than 10 calibration images. More images improve quantization quality.")

    # Create YOLO-format calibration dataset
    print("\nCreating calibration dataset...")
    dataset_yaml = create_calibration_dataset(calibration_dir, calibration_dataset_dir)
    print(f"Dataset config: {dataset_yaml}")

    # Load model
    print(f"\nLoading model from {model_path}...")
    model = YOLO(str(model_path))

    # Export to INT8 OpenVINO format
    print("\nStarting INT8 quantization export...")
    print("This may take several minutes depending on calibration dataset size...")

    start_time = time.time()

    # Export with INT8 quantization
    # Use the dataset YAML for calibration
    export_path = model.export(
        format="openvino",
        int8=True,
        data=str(dataset_yaml),  # YAML dataset config
        imgsz=640,
        half=False,  # Don't use FP16 weights (we want INT8)
        dynamic=False,  # Static shapes for better INT8 optimization
        simplify=True,  # Simplify ONNX graph
    )

    elapsed = time.time() - start_time
    print(f"\nQuantization completed in {elapsed:.1f} seconds")
    print(f"INT8 model exported to: {export_path}")

    # Show model size comparison
    original_size = model_path.stat().st_size / (1024 * 1024)

    # Find the exported model
    export_dir = Path(export_path)
    if export_dir.is_dir():
        int8_files = list(export_dir.glob("*.bin"))
        if int8_files:
            int8_size = sum(f.stat().st_size for f in int8_files) / (1024 * 1024)
            print(f"\nModel size comparison:")
            print(f"  Original (FP32): {original_size:.1f} MB")
            print(f"  INT8 OpenVINO:   {int8_size:.1f} MB")
            print(f"  Reduction:       {(1 - int8_size/original_size)*100:.1f}%")

    print("\nNext steps:")
    print("1. Move the INT8 model to weights/icon_detect/model_int8_openvino_model/")
    print("2. Update detector to use the INT8 model")
    print("3. Run benchmarks to compare FP16 vs INT8 inference speed")

    return 0

if __name__ == "__main__":
    sys.exit(main())
