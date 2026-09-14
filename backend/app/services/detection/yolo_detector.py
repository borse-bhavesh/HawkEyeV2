from typing import Optional
from ultralytics import YOLO
from app.services.detection.detector import Detector
from app.services.detection.models import Detection, BoundingBox
from app.services.video_frame import VideoFrame
from app.services.detection.config import DetectionConfig
from app.services.detection.performance_config import DetectionPerformanceConfig

class YOLODetector(Detector):
    """
    Detector implementation using Ultralytics YOLO.
    """
    
    def __init__(
        self, 
        config: DetectionConfig,
        performance_config: Optional[DetectionPerformanceConfig] = None
    ):
        self.config = config
        self.performance_config = performance_config or DetectionPerformanceConfig()
        
        # Load the model exactly once during initialization
        self.model = YOLO(self.config.model_name)
        
    def detect(self, frame: VideoFrame) -> list[Detection]:
        # Build inference kwargs based on performance configuration
        kwargs = {
            "verbose": False,
            "imgsz": self.performance_config.image_size,
            "half": self.performance_config.half_precision
        }
        
        # If device is "auto", we omit the parameter to let Ultralytics choose natively.
        if self.performance_config.device != "auto":
            kwargs["device"] = self.performance_config.device
            
        # Run inference
        # YOLO returns a list of results (one per image since we pass a single image)
        results = self.model(frame.image, **kwargs)
        
        detections = []
        
        if not results:
            return []
            
        # Extract the first result (since we passed a single frame)
        result = results[0]
        
        if result.boxes is None or len(result.boxes) == 0:
            return []
            
        for box in result.boxes:
            confidence = float(box.conf[0].item())
            
            # Filter by confidence threshold
            if confidence < self.config.confidence_threshold:
                continue
                
            coords = box.xyxy[0].tolist()
            class_id = int(box.cls[0].item())
            class_name = str(result.names[class_id])
            
            bbox = BoundingBox(
                x1=coords[0],
                y1=coords[1],
                x2=coords[2],
                y2=coords[3]
            )
            
            detection = Detection(
                class_id=class_id,
                class_name=class_name,
                confidence=confidence,
                bounding_box=bbox
            )
            
            detections.append(detection)
            
        return detections
