from collections import Counter
import io
import json
from pathlib import Path
import zipfile

from safetensors.torch import load, save
import torch
from torch import nn

from .training_data import image_input, read_rows, scores, split_rows


def network(manifest):
    labels = manifest["labels"]
    if not 2 <= len(labels) <= 32 or any(not isinstance(label, str) or len(label) > 100 for label in labels):
        raise ValueError("分类模型标签超限")
    if manifest["trainer_id"] == "text-classifier-v1":
        if not 1 <= len(manifest["vocabulary"]) <= 2048:
            raise ValueError("词表超限")
        return nn.Linear(len(manifest["vocabulary"]), len(labels))
    return nn.Sequential(nn.Conv2d(3, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                         nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d((4, 4)), nn.Flatten(), nn.Linear(512, len(labels)))


def tensors(rows, manifest):
    if manifest["trainer_id"] == "text-classifier-v1":
        vocabulary = {char: index for index, char in enumerate(manifest["vocabulary"])}
        x = torch.zeros((len(rows), len(vocabulary)))
        for index, row in enumerate(rows):
            for char, count in Counter(row["text"][:4096]).items():
                if char in vocabulary:
                    x[index, vocabulary[char]] = count
        x = x / x.sum(dim=1, keepdim=True).clamp(min=1)
    else:
        x = torch.tensor([row["pixels"] for row in rows], dtype=torch.float32).reshape(-1, 32, 32, 3).permute(0, 3, 1, 2) / 255
    y = torch.tensor([manifest["labels"].index(row["label"]) for row in rows], dtype=torch.long)
    return x, y


def load_model(path, device):
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        model = network(manifest)
        model.load_state_dict(load(archive.read("weights.safetensors")), strict=True)
    return model.to(device), manifest


class Classifier:
    def __init__(self, spec, runtime):
        self.spec, self.runtime, self.device = spec, runtime, runtime.device
        self.model = self.manifest = None
        if spec.get("model_path"):
            self.model, self.manifest = load_model(spec["model_path"], self.device)

    def train(self):
        config = self.spec["snapshot"]["config"]
        rows = read_rows(self.spec)
        train, validation = split_rows(rows, config["validation_ratio"], config["seed"])
        if self.model is None:
            self.manifest = {"format_version": 1, "trainer_id": self.spec["snapshot"]["trainer_id"], "labels": sorted({row["label"] for row in rows})}
            if self.manifest["trainer_id"] == "text-classifier-v1":
                self.manifest["vocabulary"] = [char for char, count in Counter("".join(row["text"][:4096] for row in train)).most_common(2048)]
            self.model = network(self.manifest).to(self.device)
        x, y = tensors(train, self.manifest); vx, vy = tensors(validation, self.manifest)
        self.runtime.log(f"训练 {len(train)} 条，验证 {len(validation)} 条；设备 {self.device}")
        optimizer = torch.optim.Adam(self.model.parameters(), lr=config["learning_rate"])
        criterion = nn.CrossEntropyLoss()
        step = 0
        for epoch in range(1, config["epochs"] + 1):
            self.model.train(); total = 0; correct = 0
            indices = torch.randperm(len(train))
            for start in range(0, len(train), config["batch_size"]):
                self.runtime.check_stop()
                batch = indices[start:start + config["batch_size"]]
                bx, by = x[batch].to(self.device), y[batch].to(self.device)
                optimizer.zero_grad(); logits = self.model(bx); loss = criterion(logits, by)
                loss.backward(); optimizer.step(); step += 1
                total += loss.item() * len(batch); correct += (logits.argmax(-1) == by).sum().item()
            self.model.eval()
            with torch.no_grad():
                output = self.model(vx.to(self.device)); val_loss = criterion(output, vy.to(self.device)).item()
                accuracy = (output.argmax(-1).cpu() == vy).float().mean().item()
            self.runtime.emit("metric", {"epoch": epoch, "step": step, "loss": total / len(train), "accuracy": correct / len(train), "val_loss": val_loss, "val_accuracy": accuracy})
        self.runtime.check_stop()
        with zipfile.ZipFile(self.runtime.root / "artifact.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(self.manifest, ensure_ascii=False))
            archive.writestr("weights.safetensors", save({key: value.detach().cpu().contiguous() for key, value in self.model.state_dict().items()}))
        result = scores(self.manifest["labels"], vy.tolist(), output.argmax(-1).cpu().tolist())
        return {**result, "validation_samples": len(validation), "training_samples": len(train), "device": str(self.device), "validation_loss": val_loss}

    def evaluate(self):
        rows = read_rows(self.spec); x, y = tensors(rows, self.manifest)
        predicted = []
        self.model.eval()
        with torch.no_grad():
            for start in range(0, len(rows), 32):
                self.runtime.check_stop(); predicted.extend(self.model(x[start:start + 32].to(self.device)).argmax(-1).cpu().tolist())
        return {**scores(self.manifest["labels"], y.tolist(), predicted), "device": str(self.device)}

    def predict(self, payload):
        row = {"label": self.manifest["labels"][0]}
        if self.manifest["trainer_id"] == "text-classifier-v1":
            row["text"] = payload["text"]
        else:
            row["pixels"] = image_input(payload["image_base64"])
        x, _ = tensors([row], self.manifest); self.model.eval()
        with torch.no_grad():
            probabilities = self.model(x.to(self.device)).softmax(-1)[0].cpu().tolist()
        index = max(range(len(probabilities)), key=probabilities.__getitem__)
        return {"label": self.manifest["labels"][index], "scores": dict(zip(self.manifest["labels"], probabilities))}
