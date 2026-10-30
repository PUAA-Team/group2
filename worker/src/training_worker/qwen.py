import json
import math
import os
from pathlib import Path
import zipfile

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

from .training_data import read_rows, split_rows

REPO = "Qwen/Qwen3-0.6B"
REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"


class Qwen:
    def __init__(self, spec, runtime):
        self.spec, self.runtime = spec, runtime
        snapshot = spec["snapshot"]
        if snapshot.get("qwen_revision") != REVISION:
            raise ValueError("基础模型版本不匹配")
        cache = Path(os.environ["HF_HOME"]) / "hub"
        local = cache / "models--Qwen--Qwen3-0.6B" / "snapshots" / REVISION
        if not local.is_dir():
            raise ValueError("Qwen 基础权重未缓存，请先按运行文档下载固定版本")
        runtime.log("加载 Qwen3-0.6B 固定版本")
        self.tokenizer = AutoTokenizer.from_pretrained(local, local_files_only=True, trust_remote_code=False)
        self.model = AutoModelForCausalLM.from_pretrained(local, local_files_only=True, trust_remote_code=False,
                                                        use_safetensors=True, torch_dtype=torch.bfloat16, attn_implementation="eager").to(runtime.device)
        self.model.config.use_cache = False
        if spec.get("model_path"):
            adapter = runtime.root / "adapter"; adapter.mkdir(exist_ok=True)
            with zipfile.ZipFile(spec["model_path"]) as archive:
                for name in ("adapter_config.json", "adapter_model.safetensors"):
                    (adapter / name).write_bytes(archive.read(name))
            self.model = PeftModel.from_pretrained(self.model, adapter, is_trainable=spec["kind"] == "train", local_files_only=True)
        elif spec["kind"] == "train":
            rank = snapshot["config"]["lora_rank"]
            self.model = get_peft_model(self.model, LoraConfig(task_type="CAUSAL_LM", r=rank, lora_alpha=rank * 2, target_modules=["q_proj", "v_proj"], lora_dropout=0.05))
        self.runtime.check_stop()

    def encoded(self, row):
        config = self.spec["snapshot"]["config"]
        prompt = row["instruction"] + ("\n" + row.get("input", "") if row.get("input") else "")
        prefix = self.tokenizer.apply_chat_template([{"role": "user", "content": prompt}], tokenize=True, add_generation_prompt=True, enable_thinking=False)
        response = self.tokenizer.encode(row["output"], add_special_tokens=False)[:config["max_length"] // 2] + [self.tokenizer.eos_token_id]
        prefix = prefix[-(config["max_length"] - len(response)):]
        return torch.tensor([prefix + response], device=self.runtime.device), torch.tensor([[-100] * len(prefix) + response], device=self.runtime.device)

    def validation(self, rows):
        self.model.eval(); total = tokens = 0
        with torch.no_grad():
            for row in rows:
                self.runtime.check_stop(); ids, labels = self.encoded(row)
                loss = self.model(input_ids=ids, attention_mask=torch.ones_like(ids), labels=labels).loss
                count = (labels[:, 1:] != -100).sum().item()
                total += float(loss.item()) * count; tokens += count
        return total / max(1, tokens), tokens

    def train(self):
        config = self.spec["snapshot"]["config"]
        train, validation = split_rows(read_rows(self.spec), config["validation_ratio"], config["seed"], False)
        self.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        self.model.enable_input_require_grads()
        optimizer = torch.optim.AdamW((p for p in self.model.parameters() if p.requires_grad), lr=config["learning_rate"])
        self.runtime.log(f"LoRA 可训练参数 {sum(p.numel() for p in self.model.parameters() if p.requires_grad)}；梯度累积 {config['batch_size']}")
        step = 0
        for epoch in range(1, config["epochs"] + 1):
            self.model.train(); total = 0; optimizer.zero_grad()
            for index, row in enumerate(train):
                self.runtime.check_stop(); ids, labels = self.encoded(row)
                output = self.model(input_ids=ids, attention_mask=torch.ones_like(ids), labels=labels)
                raw_loss = output.loss
                if not torch.isfinite(raw_loss):
                    raise ValueError("loss 非有限值，请调整学习率或数据")
                (raw_loss / config["batch_size"]).backward(); total += raw_loss.item()
                if (index + 1) % config["batch_size"] == 0 or index + 1 == len(train):
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0); optimizer.step(); optimizer.zero_grad(); step += 1
            val_loss, tokens = self.validation(validation)
            self.runtime.emit("metric", {"epoch": epoch, "step": step, "loss": total / len(train), "val_loss": val_loss})
        self.runtime.check_stop()
        adapter = self.runtime.root / "output"; adapter.mkdir(exist_ok=True)
        self.model.save_pretrained(adapter, safe_serialization=True, save_embedding_layers=False)
        manifest = {"format_version": 1, "trainer_id": "qwen-lora-v1", "base_model": REPO, "revision": REVISION}
        with zipfile.ZipFile(self.runtime.root / "artifact.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            for name in ("adapter_config.json", "adapter_model.safetensors"):
                archive.write(adapter / name, name)
        return {"validation_loss": val_loss, "perplexity": math.exp(min(20, val_loss)), "response_tokens": tokens,
                "training_samples": len(train), "validation_samples": len(validation), "device": str(self.runtime.device)}

    def evaluate(self):
        rows = read_rows(self.spec); loss, tokens = self.validation(rows)
        return {"loss": loss, "perplexity": math.exp(min(20, loss)), "response_tokens": tokens, "samples": len(rows)}

    def predict(self, payload):
        self.model.eval(); self.model.config.use_cache = True
        from .inference_contract import prepare_request
        profile = self.spec["snapshot"]["config"].get("inference")
        request = prepare_request(self.tokenizer, payload, profile)
        ids = torch.tensor([request["input_ids"]], device=self.runtime.device)
        generation = {}
        if request["constraint"]:
            generation = {"prefix_allowed_tokens_fn": request["constraint"], "eos_token_id": request["constraint"].eos_token_id}
        from transformers import StoppingCriteria, StoppingCriteriaList
        runtime = self.runtime
        class Cancelled(StoppingCriteria):
            def __call__(self, *args, **kwargs):
                return (runtime.root / "cancel.json").exists()
        with torch.no_grad():
            result = self.model.generate(input_ids=ids, attention_mask=torch.ones_like(ids), max_new_tokens=request["max_new_tokens"], do_sample=False,
                                         stopping_criteria=StoppingCriteriaList([Cancelled()]), **generation)
        self.runtime.check_stop()
        text = self.tokenizer.decode(result[0, ids.shape[1]:], skip_special_tokens=True)
        if request["constraint"]:
            if text not in profile["labels"]:
                raise ValueError("分类输出未满足部署标签约束")
            return {"text": text, "label": text}
        return {"text": text}
