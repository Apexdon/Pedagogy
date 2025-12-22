"""
Download OmniParser v2 Models

This script downloads the OmniParser v2 models from Hugging Face:
- icon_detect: YOLOv8 model for UI element detection
- icon_caption_florence: Florence-2 model for UI element captioning

Usage:
    python scripts/download_omniparser.py

The models will be downloaded to the 'weights' directory.
"""

import os
import sys
from pathlib import Path


def download_omniparser_models(weights_dir: str = "weights"):
    """
    Download OmniParser v2 models from Hugging Face.

    Args:
        weights_dir: Directory to save the models
    """
    try:
        from huggingface_hub import hf_hub_download, snapshot_download
    except ImportError:
        print("Error: huggingface-hub package not installed.")
        print("Install it with: pip install huggingface-hub")
        sys.exit(1)

    weights_path = Path(weights_dir)
    weights_path.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Downloading OmniParser v2 Models")
    print("=" * 60)
    print(f"Target directory: {weights_path.absolute()}")
    print()

    # Model repository
    repo_id = "microsoft/OmniParser-v2.0"

    # Files to download for icon detection
    icon_detect_files = [
        "icon_detect/train_args.yaml",
        "icon_detect/model.pt",
        "icon_detect/model.yaml",
    ]

    # Files to download for icon captioning (Florence-2)
    icon_caption_files = [
        "icon_caption/config.json",
        "icon_caption/generation_config.json",
        "icon_caption/model.safetensors",
        "icon_caption/preprocessor_config.json",
        "icon_caption/processing_florence2.py",
        "icon_caption/tokenizer.json",
        "icon_caption/tokenizer_config.json",
    ]

    # Download icon detection model
    print("[1/2] Downloading icon detection model (YOLOv8)...")
    print("-" * 40)

    icon_detect_dir = weights_path / "icon_detect"
    icon_detect_dir.mkdir(exist_ok=True)

    for file_path in icon_detect_files:
        try:
            print(f"  Downloading: {file_path}")
            hf_hub_download(
                repo_id=repo_id,
                filename=file_path,
                local_dir=weights_path
            )
            print(f"  [OK] Downloaded: {file_path}")
        except Exception as e:
            print(f"  [FAIL] Failed to download {file_path}: {e}")

    print()

    # Download icon caption model (Florence-2)
    print("[2/2] Downloading icon caption model (Florence-2)...")
    print("-" * 40)

    for file_path in icon_caption_files:
        try:
            print(f"  Downloading: {file_path}")
            hf_hub_download(
                repo_id=repo_id,
                filename=file_path,
                local_dir=weights_path
            )
            print(f"  [OK] Downloaded: {file_path}")
        except Exception as e:
            print(f"  [FAIL] Failed to download {file_path}: {e}")

    # Rename icon_caption to icon_caption_florence for consistency
    icon_caption_dir = weights_path / "icon_caption"
    icon_caption_florence_dir = weights_path / "icon_caption_florence"

    if icon_caption_dir.exists() and not icon_caption_florence_dir.exists():
        print()
        print("Renaming icon_caption -> icon_caption_florence...")
        icon_caption_dir.rename(icon_caption_florence_dir)
        print("[OK] Renamed successfully")

    print()
    print("=" * 60)
    print("Download Complete!")
    print("=" * 60)
    print()
    print("Model locations:")
    print(f"  Icon Detection:  {weights_path / 'icon_detect' / 'model.pt'}")
    print(f"  Icon Caption:    {weights_path / 'icon_caption_florence'}")
    print()
    print("To use OmniParser, ensure your config has:")
    print("  CV_DETECTION_BACKEND=omniparser")
    print("  OMNIPARSER_ICON_DETECT_PATH=weights/icon_detect/model.pt")
    print("  OMNIPARSER_ICON_CAPTION_PATH=weights/icon_caption_florence")


def verify_models(weights_dir: str = "weights"):
    """
    Verify that OmniParser models are downloaded correctly.
    """
    weights_path = Path(weights_dir)

    required_files = [
        "icon_detect/model.pt",
        "icon_caption_florence/config.json",
        "icon_caption_florence/model.safetensors",
    ]

    print("Verifying OmniParser models...")
    print("-" * 40)

    all_present = True
    for file_path in required_files:
        full_path = weights_path / file_path
        if full_path.exists():
            size_mb = full_path.stat().st_size / (1024 * 1024)
            print(f"  [OK] {file_path} ({size_mb:.1f} MB)")
        else:
            print(f"  [MISSING] {file_path}")
            all_present = False

    print()
    if all_present:
        print("[OK] All OmniParser models are present!")
    else:
        print("[WARN] Some models are missing. Run download_omniparser.py to download them.")

    return all_present


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download OmniParser v2 models")
    parser.add_argument(
        "--weights-dir",
        default="weights",
        help="Directory to save models (default: weights)"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing models, don't download"
    )

    args = parser.parse_args()

    if args.verify_only:
        verify_models(args.weights_dir)
    else:
        download_omniparser_models(args.weights_dir)
        verify_models(args.weights_dir)
