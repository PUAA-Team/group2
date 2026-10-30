import hashlib
import json
from pathlib import Path
import secrets
import urllib.error
import urllib.request

from .client import WorkerError


def open_binary(client, request, timeout=60):
    try:
        return client.opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        try:
            problem = json.load(error).get("error", {})
        except (ValueError, KeyError):
            problem = {}
        raise WorkerError(error.code, problem.get("code", "TRANSFER_ERROR"), problem.get("message", "文件传输失败")) from None
    except (OSError, urllib.error.URLError, TimeoutError):
        raise WorkerError(0, "NETWORK_ERROR", "文件传输暂时不可用") from None


def download(client, path, sha, root):
    if not sha or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("文件摘要无效")
    root.mkdir(parents=True, exist_ok=True)
    target = root / sha
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == sha:
        return target
    request = urllib.request.Request(client.controller + "/api/worker/v1" + path, headers={"Authorization": "Bearer " + client.key})
    staged = root / (sha + ".download")
    with open_binary(client, request) as response, staged.open("wb") as stream:
        size, digest = 0, hashlib.sha256()
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > 64 * 1024 * 1024:
                raise ValueError("下载文件超过限制")
            digest.update(chunk); stream.write(chunk)
    if digest.hexdigest() != sha:
        staged.unlink(missing_ok=True)
        raise ValueError("下载文件校验失败")
    staged.replace(target)
    return target


def upload(client, execution_id, path):
    boundary = "worker" + secrets.token_hex(16)
    content = path.read_bytes()
    if len(content) > 64 * 1024 * 1024:
        raise ValueError("模型产物超过 64 MiB")
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"artifact.zip\"\r\nContent-Type: application/zip\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(client.controller + f"/api/worker/v1/executions/{execution_id}/artifact", data=body,
                                     headers={"Authorization": "Bearer " + client.key, "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with open_binary(client, request) as response:
        return json.load(response)["data"]
