"""在独立目录复核原始 Worker 程序；只访问回环地址，不安装训练依赖。"""
import argparse
import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from zipfile import ZipFile

REPO = Path(__file__).resolve().parents[2]
SUPPORT = REPO / 'docs/需求调研+需求建模/初步提交材料/支撑材料'
PORT = 8875
BASE = f'http://127.0.0.1:{PORT}'
TOKEN = 'local-review-only-20261020'


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def api(path, body=None, token=TOKEN):
    data = None if body is None else json.dumps(body).encode('utf-8')
    request = urllib.request.Request(BASE + path, data=data,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def prepare(work):
    runtime = work / 'worker'
    runtime.mkdir(parents=True, exist_ok=False)
    source = SUPPORT / 'worker_agent.zip'
    with ZipFile(source) as archive:
        for entry in archive.infolist():
            relative = Path(entry.filename)
            target = (runtime / relative).resolve()
            if not target.is_relative_to(runtime.resolve()):
                raise ValueError('压缩包路径越界')
            if entry.is_dir() or '__pycache__' in relative.parts:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(archive.read(entry))
    # 仅调整隔离副本的环境配置，代码和原 ZIP 保持原样。
    catalog_path = runtime / 'config/datasets.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    catalog = {key: value for key, value in catalog.items()
               if (catalog_path.parent / value['path']).is_file()}
    dump(catalog_path, catalog)
    gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,driver_version',
        '--format=csv,noheader,nounits'], text=True).strip()
    dump(runtime / 'config/review.json', {
        'worker_id': 'review-4060-20261020', 'worker_name': '本机 RTX 4060 接入验证',
        'server_url': BASE, 'token': TOKEN, 'poll_seconds': 1,
        'runtimes': ['stdlib-smoke-v1'], 'models': []})
    dump(work / 'preparation.json', {
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'runtime': str(runtime), 'gpu': gpu, 'datasets': list(catalog),
        'code_modified': False, 'new_packages_installed': False,
        'omitted': ['__pycache__', '压缩包未包含的完整酒店数据集配置'],
        'training_weights_present': False})
    print(json.dumps({'runtime': str(runtime), 'gpu': gpu, 'datasets': len(catalog)}, ensure_ascii=False))


def verify(work):
    evidence = {'date': '2026-10-20', 'base': BASE, 'checks': []}
    def check(name, passed, detail):
        evidence['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})
        if not passed:
            dump(work / 'verification.json', evidence)
            raise AssertionError(name)
    status, workers = api('/api/workers')
    check('节点注册与硬件探测', status == 200 and len(workers) == 1 and
          workers[0]['online'] and '4060' in workers[0]['gpus'][0]['name'], workers)
    first = workers[0]['last_heartbeat']
    time.sleep(3)
    _, workers = api('/api/workers')
    check('连续心跳更新', workers[0]['last_heartbeat'] > first,
          {'before': first, 'after': workers[0]['last_heartbeat']})
    status, result = api('/api/workers', token='invalid-review-token')
    check('无效凭据拒绝', status == 401, {'status': status, 'result': result})
    status, datasets = api('/api/datasets')
    check('数据目录加载', status == 200 and len(datasets) == 5, list(datasets))
    task_body = {'task_type': 'gpu_dataset_profile', 'dataset_id': 'chnsenticorp-binary-01',
                 'required_runtime': 'stdlib-smoke-v1', 'required_memory_mb': 1,
                 'params': {'text_column': 'review', 'label_column': 'label', 'timeout_seconds': 30}}
    status, created = api('/api/tasks', task_body)
    check('异步任务受理', status == 201 and created['status'] == 'QUEUED', created)
    task_id = created['task_id']
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        _, task = api('/api/tasks/' + task_id)
        if task['status'] in ['SUCCEEDED', 'FAILED']:
            break
        time.sleep(.5)
    check('Worker 领取与子进程执行', task['status'] == 'SUCCEEDED', task)
    result = task['result']
    check('真实样本结果回传', result['dataset']['rows'] == 30 and
          result['dataset']['labels'] == {'0': 15, '1': 15}, result)
    _, events = api('/api/tasks/' + task_id + '/events')
    check('事件日志保存', len(events) >= 3, events)
    evidence['smoke_task_id'] = task_id
    for title, change in [('运行时不匹配保持排队', {'required_runtime': 'not-installed-runtime'}),
                          ('显存不足保持排队', {'required_memory_mb': 1000000})]:
        body = {**task_body, **change}
        _, created = api('/api/tasks', body)
        time.sleep(2)
        _, pending = api('/api/tasks/' + created['task_id'])
        check(title, pending['status'] == 'QUEUED', pending)
        status, cancelled = api('/api/tasks/' + created['task_id'] + '/cancel', {})
        check(title + '后取消', status == 200 and cancelled['status'] == 'CANCELLED', cancelled)
    status, invalid = api('/api/tasks', {**task_body, 'dataset_id': 'not-in-catalog'})
    check('不存在数据集拒绝受理', status == 400, invalid)
    _, workers = api('/api/workers')
    check('执行结束回到空闲', workers[0]['status'] == 'IDLE' and
          workers[0]['current_task_id'] is None, workers)
    evidence['scope'] = 'GPU 接入和数据概况任务；不执行 Qwen 训练或推理，不产生模型准确率'
    dump(work / 'verification.json', evidence)
    print(json.dumps({'passed': len(evidence['checks']), 'smoke_task_id': task_id}, ensure_ascii=False))


def offline(work):
    evidence = json.loads((work / 'verification.json').read_text(encoding='utf-8'))
    _, workers = api('/api/workers')
    result = {'name': '节点失联识别', 'passed': not workers[0]['online'], 'detail': workers}
    evidence['checks'].append(result)
    dump(work / 'verification.json', evidence)
    if not result['passed']:
        raise AssertionError('节点尚在心跳有效期内')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'verify', 'offline'])
    parser.add_argument('work', type=Path)
    args = parser.parse_args()
    globals()[args.action](args.work.resolve())
