"""
OmniParser UI Element Detector

Uses Microsoft's OmniParser v2 for detecting UI elements in screenshots.
OmniParser consists of:
1. Icon Detection Model - Finetuned YOLOv8 for detecting interactable UI elements
2. Icon Caption Model - Finetuned Florence-2 for generating element descriptions

This provides much better UI element detection than generic COCO-trained models.
"""

import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

from .data_classes import BoundingBox, UIElement, DetectionResult, DetectionTiming


# Global model cache for lazy loading
_icon_detect_model = None
_icon_caption_model = None
_icon_caption_processor = None


def _get_icon_detect_model(model_path: str, use_openvino: bool = True, use_int8: bool = False):
    """
    Get or load the icon detection model (YOLOv8) with caching.

    Args:
        model_path: Path to the YOLOv8 .pt model file
        use_openvino: Whether to export and use OpenVINO format for faster CPU inference
        use_int8: Whether to use INT8 quantized model (requires model_int8_openvino_model/)

    Returns:
        Loaded YOLO model (OpenVINO or PyTorch)
    """
    global _icon_detect_model
    import os

    if _icon_detect_model is None:
        from ultralytics import YOLO

        if use_openvino:
            # Check for INT8 model first (2-4x faster than FP16)
            int8_dir = model_path.replace('.pt', '_int8_openvino_model')
            fp16_dir = model_path.replace('.pt', '_openvino_model')

            if use_int8 and os.path.isdir(int8_dir):
                # Load INT8 quantized model
                print(f"[OmniParser] Loading INT8 OpenVINO model from {int8_dir}")
                _icon_detect_model = YOLO(int8_dir, task='detect')
            elif os.path.isdir(fp16_dir):
                # Load existing FP16 OpenVINO model
                print(f"[OmniParser] Loading FP16 OpenVINO model from {fp16_dir}")
                _icon_detect_model = YOLO(fp16_dir, task='detect')
            else:
                # Export to OpenVINO FP16 format (one-time operation)
                print(f"[OmniParser] Exporting {model_path} to OpenVINO format...")
                try:
                    pt_model = YOLO(model_path)
                    pt_model.export(format='openvino', half=True)
                    print(f"[OmniParser] OpenVINO export complete")
                    _icon_detect_model = YOLO(fp16_dir)
                except Exception as e:
                    print(f"[OmniParser] OpenVINO export failed: {e}")
                    print(f"[OmniParser] Falling back to PyTorch model")
                    _icon_detect_model = YOLO(model_path)

            # Note: Warmup disabled - causes [Errno 22] on some systems
            # The first real inference will include warmup overhead
        else:
            _icon_detect_model = YOLO(model_path)

    return _icon_detect_model


def _get_icon_caption_model(model_path: str, device: str = "cpu"):
    """
    Get or load the icon caption model (Florence-2) with caching.
    """
    global _icon_caption_model, _icon_caption_processor

    if _icon_caption_model is None:
        from transformers import AutoProcessor, AutoModelForCausalLM
        import torch

        _icon_caption_processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=True
        )
        _icon_caption_model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32
        )

        if device == "cuda" and torch.cuda.is_available():
            _icon_caption_model = _icon_caption_model.to("cuda")

    return _icon_caption_model, _icon_caption_processor


# UI element type mapping based on common UI patterns
# OmniParser detects generic "icon" class, we can infer types from captions
CAPTION_TO_UI_TYPE = {
    "button": "button",
    "click": "button",
    "submit": "button",
    "search": "search_box",
    "input": "text_input",
    "text field": "text_input",
    "textbox": "text_input",
    "checkbox": "checkbox",
    "check": "checkbox",
    "radio": "radio_button",
    "dropdown": "dropdown",
    "select": "dropdown",
    "menu": "menu",
    "link": "link",
    "tab": "tab",
    "icon": "icon",
    "image": "image",
    "logo": "logo",
    "close": "close_button",
    "minimize": "minimize_button",
    "maximize": "maximize_button",
    "scroll": "scrollbar",
    "slider": "slider",
    "toggle": "toggle",
    "switch": "toggle",
}


def infer_element_type(caption: str) -> str:
    """
    Infer UI element type from caption text.
    """
    caption_lower = caption.lower()

    for keyword, element_type in CAPTION_TO_UI_TYPE.items():
        if keyword in caption_lower:
            return element_type

    return "interactive_element"


class OmniParserDetector:
    """
    OmniParser-based UI element detector.

    Uses Microsoft's OmniParser v2 models:
    - icon_detect: YOLOv8 finetuned for UI element detection
    - icon_caption_florence: Florence-2 finetuned for UI element captioning
    """

    def __init__(
        self,
        icon_detect_path: str = "weights/icon_detect/model.pt",
        icon_caption_path: str = "weights/icon_caption_florence",
        confidence_threshold: float = 0.3,
        iou_threshold: float = 0.45,
        device: Optional[str] = None,
        enable_captioning: bool = True,
        use_openvino: bool = True,
        use_int8: bool = False
    ):
        """
        Initialize the OmniParser detector.

        Args:
            icon_detect_path: Path to icon detection model (YOLOv8)
            icon_caption_path: Path to icon caption model (Florence-2)
            confidence_threshold: Minimum confidence for detections
            iou_threshold: IoU threshold for NMS
            device: Device to run on ("cpu", "cuda"). Auto-detected if None.
            enable_captioning: Whether to generate captions for detected elements
            use_openvino: Whether to use OpenVINO for faster CPU inference (3-4x speedup)
            use_int8: Whether to use INT8 quantized model for even faster inference (2-4x over FP16)
        """
        self.icon_detect_path = icon_detect_path
        self.icon_caption_path = icon_caption_path
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.enable_captioning = enable_captioning
        self.use_openvino = use_openvino
        self.use_int8 = use_int8

        # Auto-detect device
        if device is None:
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Disable OpenVINO if using CUDA (GPU is faster)
        if self.device == "cuda":
            self.use_openvino = False

        self._detect_model = None
        self._caption_model = None
        self._caption_processor = None

    @property
    def detect_model(self):
        """Lazy-load the detection model."""
        if self._detect_model is None:
            self._detect_model = _get_icon_detect_model(
                self.icon_detect_path,
                use_openvino=self.use_openvino,
                use_int8=self.use_int8
            )
        return self._detect_model

    @property
    def caption_model(self):
        """Lazy-load the caption model."""
        if self._caption_model is None and self.enable_captioning:
            self._caption_model, self._caption_processor = _get_icon_caption_model(
                self.icon_caption_path,
                self.device
            )
        return self._caption_model

    @property
    def caption_processor(self):
        """Get the caption processor."""
        if self._caption_processor is None and self.enable_captioning:
            self._caption_model, self._caption_processor = _get_icon_caption_model(
                self.icon_caption_path,
                self.device
            )
        return self._caption_processor

    def detect(
        self,
        image: np.ndarray,
        generate_captions: bool = True
    ) -> DetectionResult:
        """
        Detect UI elements in an image.

        Args:
            image: BGR numpy array (OpenCV format)
            generate_captions: Whether to generate captions for detected elements

        Returns:
            DetectionResult with detected UIElements
        """
        start_time = time.perf_counter()

        # Debug logging
        height, width = image.shape[:2]
        print(f"[OmniParser] Detecting on image: {width}x{height}, conf={self.confidence_threshold}")

        # Run icon detection
        # Only use half precision (FP16) if OpenVINO is enabled or using GPU
        # FP16 on CPU without OpenVINO causes extreme slowdown (20+ minutes!)
        use_half = self.use_openvino or self.device == "cuda"

        predict_start = time.perf_counter()
        results = self.detect_model.predict(
            image,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            verbose=False,
            half=use_half,
            max_det=100  # Limit detections (default 300) - UI screens rarely have >50 elements
        )
        predict_time = (time.perf_counter() - predict_start) * 1000

        # Extract Ultralytics timing breakdown (preprocess, inference, postprocess in ms)
        detection_timing = None
        if results and len(results) > 0 and hasattr(results[0], 'speed'):
            speed = results[0].speed  # Dict with 'preprocess', 'inference', 'postprocess' in ms
            detection_timing = DetectionTiming(
                preprocess_ms=speed.get('preprocess', 0.0),
                inference_ms=speed.get('inference', 0.0),
                postprocess_ms=speed.get('postprocess', 0.0),
                total_ms=speed.get('preprocess', 0.0) + speed.get('inference', 0.0) + speed.get('postprocess', 0.0)
            )
            print(f"[OmniParser] YOLO predict() took {predict_time:.0f}ms (half={use_half}) | "
                  f"pre:{detection_timing.preprocess_ms:.0f}ms inf:{detection_timing.inference_ms:.0f}ms post:{detection_timing.postprocess_ms:.0f}ms")
        else:
            print(f"[OmniParser] YOLO predict() took {predict_time:.0f}ms (half={use_half})")

        elements: List[UIElement] = []

        if results and len(results) > 0:
            result = results[0]

            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes
                print(f"[OmniParser] Found {len(boxes)} detections")

                # Collect all boxes first
                box_data = []
                for i in range(len(boxes)):
                    box = boxes.xyxy[i].cpu().numpy()
                    confidence = float(boxes.conf[i].cpu().numpy())
                    class_id = int(boxes.cls[i].cpu().numpy())
                    class_name = result.names.get(class_id, f"class_{class_id}")

                    print(f"[OmniParser]   Detection {i}: conf={confidence:.3f}, class={class_name}")
                    box_data.append({
                        "box": box,
                        "confidence": confidence,
                        "class_id": class_id,
                        "class_name": class_name
                    })

                # Generate captions if enabled
                captions = []
                if generate_captions and self.enable_captioning and len(box_data) > 0:
                    captions = self._generate_captions(image, box_data)

                # Create UI elements
                for i, data in enumerate(box_data):
                    box = data["box"]

                    bbox = BoundingBox(
                        x1=int(box[0]),
                        y1=int(box[1]),
                        x2=int(box[2]),
                        y2=int(box[3])
                    )

                    # Get caption if available
                    caption = captions[i] if i < len(captions) else None

                    # Infer element type from caption or use default
                    if caption:
                        element_type = infer_element_type(caption)
                    else:
                        element_type = "interactive_element"

                    element = UIElement(
                        element_id=str(uuid.uuid4()),
                        element_type=element_type,
                        bbox=bbox,
                        confidence=data["confidence"],
                        label=caption,
                        metadata={
                            "class_id": data["class_id"],
                            "class_name": data["class_name"],
                            "detector": "omniparser"
                        }
                    )
                    elements.append(element)
            else:
                print(f"[OmniParser] No detections found at conf={self.confidence_threshold}")

        processing_time = (time.perf_counter() - start_time) * 1000
        height, width = image.shape[:2]

        return DetectionResult(
            elements=elements,
            processing_time_ms=processing_time,
            model_name="omniparser-v2",
            image_size=(width, height),
            timing=detection_timing
        )

    def _generate_captions(
        self,
        image: np.ndarray,
        box_data: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Generate captions for detected UI elements using Florence-2.

        Args:
            image: Full image (BGR numpy array)
            box_data: List of detection data with bounding boxes

        Returns:
            List of caption strings
        """
        if not self.enable_captioning:
            return []

        try:
            import torch
            from PIL import Image

            # Convert BGR to RGB and create PIL image
            rgb_image = image[:, :, ::-1]
            pil_image = Image.fromarray(rgb_image)

            captions = []

            for data in box_data:
                box = data["box"]
                x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])

                # Crop the region
                cropped = pil_image.crop((x1, y1, x2, y2))

                # Skip very small regions
                if cropped.width < 10 or cropped.height < 10:
                    captions.append(None)
                    continue

                # Generate caption using Florence-2
                caption = self._caption_single_element(cropped)
                captions.append(caption)

            return captions

        except Exception as e:
            print(f"Error generating captions: {e}")
            return [None] * len(box_data)

    def _caption_single_element(self, cropped_image) -> Optional[str]:
        """
        Generate caption for a single cropped UI element.

        Args:
            cropped_image: PIL Image of the cropped element

        Returns:
            Caption string or None
        """
        try:
            import torch

            # Prepare input
            prompt = "<CAPTION>"
            inputs = self.caption_processor(
                text=prompt,
                images=cropped_image,
                return_tensors="pt"
            )

            # Move to device
            if self.device == "cuda":
                inputs = {k: v.to("cuda") for k, v in inputs.items()}

            # Generate caption
            with torch.no_grad():
                generated_ids = self.caption_model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=50,
                    do_sample=False
                )

            # Decode
            generated_text = self.caption_processor.batch_decode(
                generated_ids,
                skip_special_tokens=True
            )[0]

            # Clean up the caption
            caption = generated_text.replace(prompt, "").strip()

            return caption if caption else None

        except Exception as e:
            print(f"Error captioning element: {e}")
            return None

    def detect_without_captions(self, image: np.ndarray) -> DetectionResult:
        """
        Detect UI elements without generating captions (faster).

        Args:
            image: BGR numpy array

        Returns:
            DetectionResult
        """
        return self.detect(image, generate_captions=False)

    def get_model_info(self) -> Dict:
        """
        Get information about the loaded models.
        """
        return {
            "icon_detect_path": self.icon_detect_path,
            "icon_caption_path": self.icon_caption_path,
            "confidence_threshold": self.confidence_threshold,
            "iou_threshold": self.iou_threshold,
            "device": self.device,
            "captioning_enabled": self.enable_captioning,
            "openvino_enabled": self.use_openvino,
            "detect_model_loaded": self._detect_model is not None,
            "caption_model_loaded": self._caption_model is not None
        }

    def is_loaded(self) -> bool:
        """Check if detection model is loaded."""
        return self._detect_model is not None


def create_omniparser_detector_from_settings(settings) -> OmniParserDetector:
    """
    Factory function to create detector from app settings.

    Args:
        settings: Application settings object

    Returns:
        Configured OmniParserDetector
    """
    return OmniParserDetector(
        icon_detect_path=settings.OMNIPARSER_ICON_DETECT_PATH,
        icon_caption_path=settings.OMNIPARSER_ICON_CAPTION_PATH,
        confidence_threshold=settings.OMNIPARSER_CONFIDENCE_THRESHOLD,
        iou_threshold=settings.OMNIPARSER_IOU_THRESHOLD,
        device="cuda" if settings.OCR_USE_GPU else "cpu",
        enable_captioning=settings.OMNIPARSER_ENABLE_CAPTIONING,
        use_openvino=getattr(settings, 'OMNIPARSER_USE_OPENVINO', True),
        use_int8=getattr(settings, 'OMNIPARSER_USE_INT8', False)
    )
