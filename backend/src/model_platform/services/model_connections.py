import ipaddress
import json
import os
import re
import secrets
import socket
from time import monotonic
from urllib.parse import urlsplit

import httpx

from ..administration_models import ModelConnection
from ..database import new_id, utcnow
from ..errors import Problem
from .common import audit, commit, revision_update, serialize


def connection_view(item):
    return {**serialize(item, exclude={"secret_ref"}), "credential_set": bool(item.secret_ref)}


def secret_path(settings, reference):
    if not re.fullmatch(r"[a-f0-9]{32}\.key", reference):
        raise Problem(503, "CREDENTIAL_NOT_READY", "模型连接凭据不可读")
    root = settings.runtime_dir / "private/connections"
    path = root / reference
    if path.resolve().parent != root.resolve():
        raise Problem(503, "CREDENTIAL_NOT_READY", "模型连接凭据不可读")
    return path


def store_secret(settings, secret):
    root = settings.runtime_dir / "private/connections"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    reference = secrets.token_hex(16) + ".key"
    path = secret_path(settings, reference)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="ascii") as stream:
        stream.write(secret)
    return reference


def get_connection(db, connection_id):
    connection = db.get(ModelConnection, connection_id)
    if connection is None:
        raise Problem(404, "NOT_FOUND", "模型连接不存在")
    return connection


def save_connection(db, settings, actor, payload, connection_id=None, expected=None):
    values = payload.model_dump(exclude={"secret"})
    item = get_connection(db, connection_id) if connection_id else None
    if item and item.revision != expected:
        raise Problem(412, "REVISION_MISMATCH", "模型连接已更新，请重新读取")
    reference = store_secret(settings, payload.secret) if payload.secret else None
    if reference:
        values["secret_ref"] = reference
    try:
        if item:
            revision_update(db, item, {**values, "health": {}}, expected)
        else:
            if not reference:
                raise Problem(422, "CREDENTIAL_REQUIRED", "请填写模型API密钥")
            item = ModelConnection(id=new_id("con"), created_by=actor.id, health={}, **values)
            db.add(item)
        audit(db, actor, "model_connections.update" if connection_id else "model_connections.create", item.id)
        commit(db)
    except Exception as error:
        db.rollback()
        if reference and isinstance(error, Problem):
            # 明确拒绝时清理本次文件；提交结果不明时保留现场。
            secret_path(settings, reference).unlink(missing_ok=True)
        raise
    return connection_view(item)


def validate_remote(endpoint):
    url = urlsplit(endpoint)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise Problem(422, "INVALID_ENDPOINT", "模型API需要HTTPS地址")
    try:
        addresses = socket.getaddrinfo(url.hostname, url.port or 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, ValueError):
        raise Problem(422, "INVALID_ENDPOINT", "模型API地址无法解析") from None
    if not addresses or any(not ipaddress.ip_address(record[4][0]).is_global for record in addresses):
        raise Problem(422, "INVALID_ENDPOINT", "模型API地址需要使用公网服务")


async def completion(settings, connection, messages, *, max_tokens=512):
    if not connection.active or not connection.secret_ref:
        raise Problem(409, "CONNECTION_DISABLED", "模型连接未启用或未配置凭据")
    validate_remote(connection.endpoint)
    try:
        secret = secret_path(settings, connection.secret_ref).read_text(encoding="ascii")
    except OSError:
        raise Problem(503, "CREDENTIAL_NOT_READY", "模型连接凭据不可读") from None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10), trust_env=False, follow_redirects=False) as client:
            async with client.stream("POST", connection.endpoint + "/chat/completions", headers={"Authorization": "Bearer " + secret},
                                     json={"model": connection.model, "messages": messages, "max_tokens": max_tokens, "temperature": 0}) as response:
                if response.status_code != 200:
                    raise Problem(502, "PROVIDER_ERROR", f"模型服务返回HTTP {response.status_code}")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 1024 * 1024:
                        raise Problem(502, "PROVIDER_RESPONSE_TOO_LARGE", "模型响应超过限制")
                result = json.loads(content)
                choice = result["choices"][0]
                if not isinstance(choice, dict):
                    raise ValueError("invalid choice")
                if choice.get("finish_reason") == "length":
                    raise Problem(502, "PROVIDER_OUTPUT_LIMIT", "模型回复达到输出Token上限，请提高上限后重试")
                text = choice["message"]["content"]
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("invalid content")
                return text, result.get("usage", {})
    except httpx.TimeoutException:
        raise Problem(504, "PROVIDER_TIMEOUT", "模型服务响应超时") from None
    except httpx.HTTPError:
        raise Problem(502, "PROVIDER_UNAVAILABLE", "模型服务连接失败") from None
    except (ValueError, KeyError, IndexError, TypeError):
        raise Problem(502, "PROVIDER_INVALID_RESPONSE", "模型服务响应格式无效") from None


async def test_connection(db, settings, actor, connection_id):
    item = get_connection(db, connection_id)
    started = monotonic()
    health = {"checked_at": utcnow().isoformat()}
    try:
        # 思考和正文可能共享输出额度；探测也要给模型完成短回复的空间。
        await completion(settings, item, [{"role": "user", "content": "Reply with OK."}], max_tokens=256)
        health.update(status="available", message="连接成功")
    except Problem as error:
        if error.code == "PROVIDER_OUTPUT_LIMIT":
            health.update(status="available", message="连接成功；测试回复达到输出上限", code=error.code)
        else:
            health.update(status="failed", message=error.message, code=error.code)
    health["elapsed_ms"] = round((monotonic() - started) * 1000)
    revision_update(db, item, {"health": health}, item.revision)
    audit(db, actor, "model_connections.test", item.id)
    commit(db)
    return connection_view(item)
