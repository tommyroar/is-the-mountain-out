import pytest
import torch
import torch.optim as optim
from model import ConvNextLoRAModel

def test_lora_initialization():
    """Verify ConvNextLoRAModel initializes with correct device."""
    model_wrapper = ConvNextLoRAModel(num_classes=2)
    
    if torch.backends.mps.is_available():
        assert str(model_wrapper.device) == "mps"
    else:
        assert str(model_wrapper.device) == "cpu"
    
    # Check if peft wrapped the backbone
    from peft import PeftModel
    assert isinstance(model_wrapper.model['backbone'], PeftModel)

def test_dual_input_batch_parameter_update():
    """Verify LoRA weights and classifier update after a batch training step."""
    model_wrapper = ConvNextLoRAModel(num_classes=2)
    device = model_wrapper.device
    batch_size = 4
    
    # Get initial parameters
    initial_params = {}
    for name, param in model_wrapper.model.named_parameters():
        initial_params[name] = param.clone().detach()

    # Create dummy image, weather tensor, and optimizer
    image_batch = torch.randn(batch_size, 3, 224, 224).to(device)
    weather_batch = torch.randn(batch_size, 2).to(device)
    label_batch = torch.randint(0, 2, (batch_size,)).to(device)
    optimizer = optim.Adam(model_wrapper.model.parameters(), lr=0.001)
    
    # Perform training step
    model_wrapper.train_step(image_batch, weather_batch, label_batch, optimizer)
    
    # Check if parameters updated
    updated_lora = False
    updated_classifier = False
    
    for name, param in model_wrapper.model.named_parameters():
        if 'lora_' in name:
            if not torch.equal(initial_params[name], param):
                updated_lora = True
        elif 'classifier' in name:
            if not torch.equal(initial_params[name], param):
                updated_classifier = True
    
    assert updated_lora, "LoRA parameters in backbone did not change after a batch training step"
    assert updated_classifier, "Classifier head parameters did not change after a batch training step"

def test_backbone_frozen():
    """Verify that non-LoRA backbone parameters are frozen."""
    model_wrapper = ConvNextLoRAModel(num_classes=2)
    
    for name, param in model_wrapper.model['backbone'].named_parameters():
        if 'lora_' not in name:
            assert not param.requires_grad, f"Non-LoRA backbone parameter {name} is not frozen"

def test_predict_batch():
    """Verify prediction works with a batch of dual inputs."""
    model_wrapper = ConvNextLoRAModel(num_classes=2)
    device = model_wrapper.device
    batch_size = 4
    
    image_batch = torch.randn(batch_size, 3, 224, 224).to(device)
    weather_batch = torch.randn(batch_size, 2).to(device)
    
    predictions = model_wrapper.predict(image_batch, weather_batch)
    assert predictions.shape == (batch_size,)
    for pred in predictions:
        assert pred.item() in [0, 1]
