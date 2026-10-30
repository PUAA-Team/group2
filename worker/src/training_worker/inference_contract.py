"""任务提示与固定标签解码，不依赖训练框架，便于独立核验。"""


class LabelConstraint:
    def __init__(self, tokenizer, labels, prompt_length):
        self.prompt_length = prompt_length
        self.eos_token_id = tokenizer.eos_token_id
        if not isinstance(self.eos_token_id, int) or not 2 <= len(labels) <= 32 or len(set(labels)) != len(labels):
            raise ValueError("分类标签或结束Token无效")
        self.root = {}; lengths = []
        for label in labels:
            tokens = tokenizer.encode(label, add_special_tokens=False)
            if not tokens or any(token in tokenizer.all_special_ids for token in tokens) or tokenizer.decode(tokens, skip_special_tokens=True) != label:
                raise ValueError("分类标签包含特殊Token或无法完整编码")
            node = self.root
            for token in tokens + [self.eos_token_id]:
                node = node.setdefault(token, {})
            lengths.append(len(tokens) + 1)
        self.max_new_tokens = max(lengths)

    def __call__(self, batch_id, input_ids):
        sequence = input_ids.tolist() if hasattr(input_ids, "tolist") else list(input_ids)
        node = self.root
        for token in sequence[self.prompt_length:]:
            if token not in node:
                raise ValueError("生成前缀不属于部署标签")
            node = node[token]
        return sorted(node) if node else [self.eos_token_id]


def prepare_request(tokenizer, payload, profile=None):
    profile = profile or {"mode": "generate", "instruction": "", "labels": []}
    mode = profile.get("mode", "generate")
    if mode not in {"generate", "label"}:
        raise ValueError("部署输出模式无效")
    instruction = profile.get("instruction", "")
    text = (instruction + "\n" if instruction else "") + payload["text"]
    ids = tokenizer.apply_chat_template([{"role": "user", "content": text}], tokenize=True, add_generation_prompt=True, enable_thinking=False)
    if len(ids) > 512:
        raise ValueError("输入与任务指令超过512 Token，请缩短内容")
    budget = payload.get("max_new_tokens", 32)
    constraint = LabelConstraint(tokenizer, profile.get("labels", []), len(ids)) if mode == "label" else None
    if constraint:
        if constraint.max_new_tokens > budget:
            raise ValueError("输出长度上限不足以生成完整标签及结束Token")
        budget = constraint.max_new_tokens
    return {"input_ids": ids, "max_new_tokens": budget, "constraint": constraint}
