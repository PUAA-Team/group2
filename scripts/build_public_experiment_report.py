"""从平台实际任务与独立测试记录生成报告和曲线CSV。"""
from datetime import datetime
import csv
import json
from pathlib import Path
import shutil
import sqlite3


def main():
    root = Path("D:/model-training-demo/public-experiments-20261029")
    run = json.loads((root / "experiment-run.json").read_text(encoding="utf-8"))
    source = json.loads((root / "dataset-manifest.json").read_text(encoding="utf-8"))
    if not run.get("success") or len(run.get("qwen_predictions", {})) != 128:
        raise RuntimeError("实验尚未全部完成，不能生成最终结果")
    output = Path(__file__).resolve().parents[1] / "docs/stage10"
    output.mkdir(exist_ok=True)
    connection = sqlite3.connect("file:D:/model-training-demo/backend-runtime/platform.sqlite3?mode=ro", uri=True)
    curves = []; summary = {}; results = run["results"]
    names = [("sms_5", "SMS 5epoch / LR0.01"), ("sms_25", "SMS 25epoch / LR0.03"), ("fashion_3", "Fashion 3epoch / LR0.003"), ("fashion_10", "Fashion 10epoch / LR0.003"), ("qwen_1", "Qwen LoRA 1epoch")]
    for key, name in names:
        eid, created, finished = connection.execute("SELECT id,created_at,finished_at FROM executions WHERE job_id=?", (run["jobs"][key],)).fetchone()
        elapsed = (datetime.fromisoformat(finished) - datetime.fromisoformat(created)).total_seconds()
        events = connection.execute("SELECT payload FROM execution_events WHERE execution_id=? AND type='metric' ORDER BY seq", (eid,)).fetchall()
        for (payload,) in events:
            curves.append({"experiment": key, **json.loads(payload)})
        summary[key] = {"name": name, "training": results[key], "test": results[key + "_test"], "elapsed_seconds": round(elapsed, 2)}
    connection.close()
    with (output / "curves.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["experiment", "epoch", "step", "loss", "accuracy", "val_loss", "val_accuracy"])
        writer.writeheader(); writer.writerows(curves)
    exported = {"project_id": run["project_id"], "experiments": summary, "qwen_generation_test": run["qwen_generation_test"],
                "sms_majority_baseline": run["sms_majority_baseline"], "fashion_majority_baseline": run["fashion_majority_baseline"], "jobs": run["jobs"]}
    (output / "experiment-results.json").write_text(json.dumps(exported, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copyfile(root / "dataset-manifest.json", output / "dataset-manifest.json")
    def percent(value):
        return f"{value * 100:.2f}%"
    lines = ["# 公开数据实验结果", "", "2026-10-29。全部训练、评估和推理由现有平台GPU Worker完成，结果保存在原工作空间。", "",
             f"[打开实验项目](http://127.0.0.1:8000/#/runs?project={run['project_id']}) · [曲线CSV](./curves.csv) · [完整结果](./experiment-results.json) · [数据来源与摘要](./dataset-manifest.json)", "",
             "## 数据规模与划分", "", "| 数据 | 训练 | 验证 | 独立测试 |", "| --- | ---: | ---: | ---: |",
             f"| SMS短信 | {results['sms_5']['result']['training_samples']} | {results['sms_5']['result']['validation_samples']} | {results['sms_5_test']['result']['samples']} |",
             "| Fashion-MNIST | 4800 | 1200 | 2000 |", f"| Qwen短信指令 | {results['qwen_1']['result']['training_samples']} | {results['qwen_1']['result']['validation_samples']} | 128 |", "",
             f"SMS原始5574条，规范化去重415条，保留5159条。先按标签分层划分开发/测试，再由训练器从开发池划出验证集。Qwen从同一开发池平衡抽取512条、从独立测试集平衡抽取128条。短信来源为[UCI SMS Spam Collection](https://archive.ics.uci.edu/dataset/228/sms%2Bspam%2Bcollection)，Almeida与Hidalgo，2011，CC BY4.0。", "",
             "图像保留官方训练/测试来源分离，各类抽取600张开发图和200张测试图。原始28×28灰度PNG无损保存，训练输入为32×32 RGB。数据来自[Zalando Fashion-MNIST](https://github.com/zalandoresearch/fashion-mnist)，Xiao、Rasul与Vollgraf，2017，MIT。四个官方MD5均通过。短信规范化文本与图像像素跨集合交集均为0。", "",
             "## 分类对照", "", "| 配置 | 测试样本 | Accuracy | Macro F1 | 执行耗时 |", "| --- | ---: | ---: | ---: | ---: |"]
    for key, name in names[:4]:
        item = summary[key]; score = item["test"]["result"]
        lines.append(f"| {name} | {score['samples']} | {percent(score['accuracy'])} | {score['macro_f1']:.4f} | {item['elapsed_seconds']:.1f}s |")
    baseline = run["sms_majority_baseline"]
    lines += [f"| SMS多数类基线 | {baseline['samples']} | {percent(baseline['accuracy'])} | {baseline['macro_f1']:.4f} | — |", "| Fashion多数类基线 | 2000 | 10.00% | 0.0182 | — |", "",
              "短信两组比较整体配置，训练轮数和学习率共同变化；图像两组保持数据、学习率和batch一致，比较训练轮数。随机种子统一42，所有预定结果保留，测试集未参与训练。执行耗时含准备、加载、训练及回传，未进行重复测量和显著性检验。", "",
              "## Qwen LoRA", "", "基础模型Qwen3-0.6B固定提交c1899de289a04d12100db370d81485cdf75e47ca；1epoch、微批1、梯度累积4、长度192、rank4、学习率0.0002。", ""]
    generated = run["qwen_generation_test"]
    lines += [f"128条平衡测试短信逐条经过实际服务生成ham/spam，Accuracy **{percent(generated['accuracy'])}**，Macro F1 **{generated['macro_f1']:.4f}**，无效输出 **{generated['invalid_outputs']}** 条。平衡集合多数类基线Accuracy为50%、Macro F1为0.3333。",
              f"独立JSONL的响应Token loss为{results['qwen_1_test']['result']['loss']:.5f}。该值与分类准确率分别计算。测试结束后已请求停止该GPU服务并确认退出，CPU演示服务保留。", "",
              "当前评估描述微调后的分类表现。同条件原始Qwen生成基线、更多随机种子和更大测试样本放在后续实验，不据此计算微调带来的提升幅度。", "",
              "## 混淆矩阵", ""]
    for key, title in [("sms_25_test", "SMS 25epoch"), ("fashion_10_test", "Fashion 10epoch")]:
        value = results[key]["result"]; labels = value["labels"]
        lines += [f"### {title}", "", "行表示实际类别，列表示预测类别。", "", "| 类别 | " + " | ".join(labels) + " |", "| --- | " + " | ".join("---:" for _ in labels) + " |"]
        lines += ["| " + label + " | " + " | ".join(str(number) for number in row) + " |" for label, row in zip(labels, value["confusion_matrix"])]; lines.append("")
    lines += ["## 在页面查看", "", "| 实验 | 训练曲线与日志 | 独立测试 |", "| --- | --- | --- |"]
    for key, name in names:
        lines.append(f"| {name} | [训练任务](http://127.0.0.1:8000/#/runs/{run['jobs'][key]}) | [评估任务](http://127.0.0.1:8000/#/runs/{run['jobs'][key + '_test']}) |")
    lines += ["", "## 复现", "", "D盘原始与准备文件：`D:/model-training-demo/public-experiments-20261029`。先运行`scripts/prepare_public_experiments.py`和`check_public_experiment_data.py`，再运行`run_public_experiments.py`并显式指定工作空间与操作人；完成后运行`build_public_experiment_report.py`。", "",
              "运行脚本从experiment-run.json续接已有任务，保留失败现场；不要在同一目录同时启动多个实验协调进程。数据文件均低于现有10MiB上传限制。本次没有新增依赖，也没有通过外部大模型API发送样本。", "",
              "模型仍使用首版字符线性网络、TinyCNN和LoRA。短信为英文历史语料，图像为低分辨率服装子集；当前结果适合验证平台与对照方法，企业内真实任务仍需使用业务数据重新评估。"]
    (output / "实验结果.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output / "实验结果.md"), "curves": len(curves), "experiments": len(summary)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
