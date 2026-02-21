import cv2
import torch
import numpy as np
from torchvision import transforms
from typing import Optional, Union

class WebcamStream:
    def __init__(self, source: Union[int, str], device: str = "mps"):
        self.source = source
        self.device = device if torch.backends.mps.is_available() else "cpu"
        self.cap = cv2.VideoCapture(source)
        
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize(224),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def capture_to_tensor(self) -> Optional[torch.Tensor]:
        """
        Captures a frame from the webcam, converts it to a PyTorch tensor,
        moves it to the MPS device, and returns it.
        No disk usage.
        """
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        # Convert BGR (OpenCV) to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Apply transformations and convert to tensor
        # Transforms return a tensor normally, we then move to MPS
        tensor = self.transform(frame_rgb).to(self.device)
        
        # Ensure it's in the batch format [1, 3, 224, 224]
        return tensor.unsqueeze(0)

    def release(self):
        if self.cap.isOpened():
            self.cap.release()

    def __del__(self):
        self.release()
