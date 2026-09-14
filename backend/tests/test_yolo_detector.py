import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from app.services.detection.yolo_detector import YOLODetector
from app.services.detection.models import Detection
from app.services.video_frame import VideoFrame
from app.services.detection.config import DetectionConfig
from app.services.detection.performance_config import DetectionPerformanceConfig

@pytest.fixture
def mock_yolo():
    with patch("app.services.detection.yolo_detector.YOLO") as MockYOLO:
        yield MockYOLO

def create_mock_result(boxes_data):
    """Helper to create a fake YOLO result object"""
    result = MagicMock()
    result.names = {0: "person", 1: "bicycle", 2: "car"}
    
    if not boxes_data:
        result.boxes = []
        return result
        
    boxes = []
    for data in boxes_data:
        box = MagicMock()
        xyxy_mock = MagicMock()
        xyxy_mock.tolist.return_value = data["xyxy"]
        box.xyxy = [xyxy_mock]
        
        conf_mock = MagicMock()
        conf_mock.item.return_value = data["conf"]
        box.conf = [conf_mock]
        
        cls_mock = MagicMock()
        cls_mock.item.return_value = data["cls"]
        box.cls = [cls_mock]
        
        boxes.append(box)
        
    result.boxes = boxes
    return result

def test_yolo_config_accepted(mock_yolo):
    config = DetectionConfig(model_name="test.pt", confidence_threshold=0.5)
    detector = YOLODetector(config)
    assert detector.config == config

def test_yolo_detector_no_performance_config(mock_yolo):
    config = DetectionConfig(model_name="test.pt", confidence_threshold=0.5)
    detector = YOLODetector(config)
    assert isinstance(detector.performance_config, DetectionPerformanceConfig)
    assert detector.performance_config.device == "auto"

def test_yolo_model_name_comes_from_config(mock_yolo):
    config = DetectionConfig(model_name="my_model.pt")
    detector = YOLODetector(config)
    mock_yolo.assert_called_once_with("my_model.pt")

def test_yolo_model_name_still_from_config_with_perf_config(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt")
    perf_config = DetectionPerformanceConfig(device="cpu")
    detector = YOLODetector(config, performance_config=perf_config)
    mock_yolo.assert_called_once_with("dummy.pt")

def test_yolo_model_loaded_once(mock_yolo):
    config = DetectionConfig(model_name="yolo11n.pt")
    detector = YOLODetector(config)
    
    mock_yolo.assert_called_once_with("yolo11n.pt")
    
    mock_model_instance = mock_yolo.return_value
    fake_result = create_mock_result([])
    mock_model_instance.return_value = [fake_result]
    
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=np.zeros((100, 100, 3)))
    
    detector.detect(frame)
    detector.detect(frame)
    
    mock_yolo.assert_called_once_with("yolo11n.pt")
    
def test_yolo_confidence_threshold_filtering(mock_yolo):
    mock_model_instance = mock_yolo.return_value
    fake_result = create_mock_result([
        {"xyxy": [10.0, 20.0, 30.0, 40.0], "conf": 0.80, "cls": 0},
        {"xyxy": [50.0, 60.0, 70.0, 80.0], "conf": 0.50, "cls": 0},
        {"xyxy": [90.0, 10.0, 20.0, 30.0], "conf": 0.49, "cls": 0}
    ])
    mock_model_instance.return_value = [fake_result]
    
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    detector = YOLODetector(config)
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=np.zeros((100, 100, 3)))
    
    detections = detector.detect(frame)
    
    assert len(detections) == 2
    assert detections[0].confidence == 0.80
    assert detections[1].confidence == 0.50

def test_yolo_all_detections_below_threshold(mock_yolo):
    mock_model_instance = mock_yolo.return_value
    fake_result = create_mock_result([
        {"xyxy": [10.0, 20.0, 30.0, 40.0], "conf": 0.49, "cls": 0},
        {"xyxy": [50.0, 60.0, 70.0, 80.0], "conf": 0.20, "cls": 0}
    ])
    mock_model_instance.return_value = [fake_result]
    
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    detector = YOLODetector(config)
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=np.zeros((100, 100, 3)))
    
    detections = detector.detect(frame)
    
    assert detections == []

def test_yolo_multiple_detections(mock_yolo):
    mock_model_instance = mock_yolo.return_value
    fake_result = create_mock_result([
        {"xyxy": [10.0, 20.0, 30.0, 40.0], "conf": 0.9, "cls": 0},
        {"xyxy": [50.0, 60.0, 70.0, 80.0], "conf": 0.8, "cls": 2}
    ])
    mock_model_instance.return_value = [fake_result]
    
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    detector = YOLODetector(config)
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=np.zeros((100, 100, 3)))
    
    detections = detector.detect(frame)
    
    assert len(detections) == 2
    
    assert detections[0].class_id == 0
    assert detections[0].class_name == "person"
    assert detections[0].confidence == 0.9
    
    assert detections[1].class_id == 2
    assert detections[1].class_name == "car"
    assert detections[1].confidence == 0.8

def test_yolo_empty_detection(mock_yolo):
    mock_model_instance = mock_yolo.return_value
    fake_result = create_mock_result([]) # Empty boxes
    mock_model_instance.return_value = [fake_result]
    
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    detector = YOLODetector(config)
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=np.zeros((100, 100, 3)))
    
    detections = detector.detect(frame)
    
    assert detections == []

def test_yolo_inference_receives_frame_image(mock_yolo):
    mock_model_instance = mock_yolo.return_value
    fake_result = create_mock_result([])
    mock_model_instance.return_value = [fake_result]
    
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    detector = YOLODetector(config)
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert np.array_equal(args[0], img)
    assert kwargs.get("verbose") is False
    assert kwargs.get("half") is False
    assert kwargs.get("imgsz") == 640
    assert kwargs.get("half") is False

def test_yolo_device_cpu(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(device="cpu")
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert kwargs.get("device") == "cpu"
    assert kwargs.get("imgsz") == 640
    assert kwargs.get("half") is False

def test_yolo_device_cuda(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(device="cuda")
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert kwargs.get("device") == "cuda"
    assert kwargs.get("imgsz") == 640
    assert kwargs.get("half") is False

def test_yolo_device_auto_omitted(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(device="auto")
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert "device" not in kwargs
    assert kwargs.get("imgsz") == 640
    assert kwargs.get("half") is False

def test_yolo_default_imgsz(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig()
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert kwargs.get("imgsz") == 640
    assert kwargs.get("half") is False

def test_yolo_custom_imgsz_large(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(image_size=1280)
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert kwargs.get("imgsz") == 1280
    assert kwargs.get("half") is False

def test_yolo_custom_imgsz_small(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(image_size=320)
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert kwargs.get("imgsz") == 320
    assert kwargs.get("half") is False

def test_yolo_device_and_imgsz_combined(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(device="cpu", image_size=1280)
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert kwargs.get("device") == "cpu"
    assert kwargs.get("imgsz") == 1280
    assert kwargs.get("half") is False


def test_yolo_half_precision_true(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(half_precision=True)
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert kwargs.get("half") is True

def test_yolo_half_precision_false(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(half_precision=False)
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert kwargs.get("half") is False

def test_yolo_device_cpu_half_false(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(device="cpu", half_precision=False)
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert kwargs.get("device") == "cpu"
    assert kwargs.get("half") is False

def test_yolo_device_cuda_half_true(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(device="cuda", half_precision=True)
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert kwargs.get("device") == "cuda"
    assert kwargs.get("half") is True

def test_yolo_device_auto_half_true(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(device="auto", half_precision=True)
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert "device" not in kwargs
    assert kwargs.get("half") is True

def test_yolo_combined_kwargs(mock_yolo):
    config = DetectionConfig(model_name="dummy.pt", confidence_threshold=0.50)
    perf_config = DetectionPerformanceConfig(device="cuda", image_size=1280, half_precision=True)
    detector = YOLODetector(config, performance_config=perf_config)
    
    img = np.zeros((100, 100, 3))
    frame = VideoFrame(frame_number=1, timestamp_seconds=0.0, image=img)
    
    mock_model_instance = mock_yolo.return_value
    mock_model_instance.return_value = [create_mock_result([])]
    
    detector.detect(frame)
    
    mock_model_instance.assert_called_once()
    args, kwargs = mock_model_instance.call_args
    assert kwargs.get("device") == "cuda"
    assert kwargs.get("imgsz") == 1280
    assert kwargs.get("half") is True