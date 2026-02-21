import timm
import torch
import torch.nn as nn
from peft import LoraConfig, get_peft_model
from typing import List, Optional
import os

class ConvNextLoRAModel:
    def __init__(self, num_classes: int = 2, rank: int = 8, alpha: int = 16, 
                 target_modules: List[str] = ["fc1", "fc2"], device: str = "mps"):
        self.device = device if torch.backends.mps.is_available() else "cpu"
        
        # Load pretrained model
        self.base_model = timm.create_model('convnext_tiny', pretrained=True, num_classes=0, global_pool='avg')
        
        # LoRA Configuration
        self.lora_config = LoraConfig(
            r=rank,
            lora_alpha=alpha,
            target_modules=target_modules,
            lora_dropout=0.1,
            bias="none"
        )
        
        # Wrap the backbone with LoRA
        self.backbone = get_peft_model(self.base_model, self.lora_config)
        
        # Custom head for dual input (image features + weather vector)
        self.weather_dim = 2
        self.classifier = nn.Sequential(
            nn.Linear(768 + self.weather_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, num_classes)
        )
        
        self.model = nn.ModuleDict({
            'backbone': self.backbone,
            'classifier': self.classifier
        })
        self.model.to(self.device)

    def train_step(self, image_batch: torch.Tensor, weather_batch: torch.Tensor, 
                   label_batch: torch.Tensor, optimizer: torch.optim.Optimizer):
        self.model.train()
        optimizer.zero_grad()
        
        image_batch = image_batch.to(self.device)
        weather_batch = weather_batch.to(self.device)
        label_batch = label_batch.to(self.device)
        
        features = self.model['backbone'](image_batch)
        combined_input = torch.cat((features, weather_batch), dim=1)
        outputs = self.model['classifier'](combined_input)
        
        loss = torch.nn.functional.cross_entropy(outputs, label_batch)
        loss.backward()
        optimizer.step()
        
        loss_val = loss.item()
        del loss, outputs, features, combined_input, label_batch
        if self.device == "mps":
            torch.mps.empty_cache()
            
        return loss_val

    def predict(self, image_batch: torch.Tensor, weather_batch: torch.Tensor) -> torch.Tensor:
        self.model.eval()
        with torch.no_grad():
            image_batch = image_batch.to(self.device)
            weather_batch = weather_batch.to(self.device)
            features = self.model['backbone'](image_batch)
            combined_input = torch.cat((features, weather_batch), dim=1)
            outputs = self.model['classifier'](combined_input)
            _, predicted = torch.max(outputs, 1)
            return predicted

    def save_checkpoint(self, checkpoint_dir: str):
        """Saves LoRA adapters and classifier head."""
        os.makedirs(checkpoint_dir, exist_ok=True)
        self.model['backbone'].save_pretrained(checkpoint_dir)
        torch.save(self.model['classifier'].state_dict(), os.path.join(checkpoint_dir, "classifier.pt"))
        print(f"Checkpoint saved to {checkpoint_dir}")

    def load_checkpoint(self, checkpoint_dir: str):
        """Loads LoRA adapters and classifier head."""
        classifier_path = os.path.join(checkpoint_dir, "classifier.pt")
        if os.path.exists(checkpoint_dir) and os.path.exists(classifier_path):
            self.model['backbone'].load_adapter(checkpoint_dir, "default")
            self.model['classifier'].load_state_dict(torch.load(classifier_path, map_location=self.device))
            print(f"Checkpoint loaded from {checkpoint_dir}")
            return True
        return False
