from ..errors import Problem

TRAINERS = [
    {"id": "text-classifier-v1", "task_type": "text_classification", "name": "文本线性分类", "execution_available": True},
    {"id": "image-classifier-v1", "task_type": "image_classification", "name": "TinyCNN 图像分类", "execution_available": True},
    {"id": "qwen-lora-v1", "task_type": "llm_sft", "name": "Qwen LoRA", "execution_available": True},
]


def check_trainer(task_type, trainer_id):
    if not any(item["id"] == trainer_id and item["task_type"] == task_type for item in TRAINERS):
        raise Problem(422, "VALIDATION_ERROR", "任务与训练模板不匹配")
