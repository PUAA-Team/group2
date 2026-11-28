"""Stage 20B-1：部署加固回归测试（纯配置/脚本校验，不依赖数据库与 Docker）。

覆盖：compose.yaml 能力收紧与镜像固定、nginx 模板安全头与 TLS_IP 参数化、
.env.example 参数化、certbot 镜像固定、backup.sh 备份正确的库、
restore.sh 校验函数、systemd 备份定时任务、旧 IP 清理。
"""
import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy" / "server"
OLD_IP = "47.93.115.188"
MINIMAL_CAPS = {"CHOWN", "DAC_OVERRIDE", "SETGID", "SETUID"}

REQUIRED_HEADERS = [
    'X-Content-Type-Options "nosniff"',
    'X-Frame-Options "DENY"',
    'Referrer-Policy "strict-origin-when-cross-origin"',
    "Content-Security-Policy",
]


def read(path):
    return path.read_text(encoding="utf-8")


def service_block(text, name):
    """按缩进取出 compose.yaml 里某服务的配置块（含 x-control 锚）。"""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(rf"^  {name}:", line))
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^  \S", lines[i]) or re.match(r"^\S", lines[i])), len(lines))
    return "\n".join(lines[start:end])


def top_block(text, name):
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(rf"^{name}:", line))
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^\S", lines[i])), len(lines))
    return "\n".join(lines[start:end])


def run_bash(script, timeout=30):
    return subprocess.run(["bash", "-c", script], capture_output=True,
                          text=True, timeout=timeout)


# ---------- compose.yaml ----------

def test_compose_control_services_drop_capabilities():
    text = read(DEPLOY / "compose.yaml")
    control = top_block(text, "x-control")
    assert "cap_drop: [ALL]" in control
    assert "security_opt: [no-new-privileges:true]" in control
    for name in ("api", "operations", "migrate"):
        assert "<<: *control" in service_block(text, name), name


def test_compose_db_and_gateway_drop_capabilities_with_minimal_add():
    text = read(DEPLOY / "compose.yaml")
    for name in ("db", "gateway"):
        block = service_block(text, name)
        assert "cap_drop: [ALL]" in block, name
        assert "security_opt: [no-new-privileges:true]" in block, name
        added = set(re.search(r"cap_add: \[([^\]]+)\]", block).group(1).replace(" ", "").split(","))
        assert added <= MINIMAL_CAPS, (name, added)


def test_compose_images_pinned_no_latest():
    text = read(DEPLOY / "compose.yaml")
    images = re.findall(r"^\s*image: (.+)$", text, re.M)
    assert images, "compose 里没有 image 声明"
    for image in images:
        assert ":latest" not in image, image
        assert "stable-alpine" not in image, image
    gateway = service_block(text, "gateway")
    assert "image: nginx:1.30.8-alpine" in gateway
    assert "image: postgres:17-bookworm" in service_block(text, "db")


def test_compose_gateway_healthcheck_and_template_mount():
    text = read(DEPLOY / "compose.yaml")
    gateway = service_block(text, "gateway")
    assert "healthcheck:" in gateway
    assert "wget" in gateway and "/readyz" in gateway
    assert "curl" not in gateway  # alpine 镜像只有 wget，没有 curl
    assert ":/etc/nginx/templates/default.conf.template:ro" in gateway
    assert "TLS_IP: ${TLS_IP:?set TLS IP or hostname}" in gateway


# ---------- nginx 模板 ----------

def check_nginx_template(path, https):
    text = read(path)
    assert OLD_IP not in text
    for header in REQUIRED_HEADERS:
        assert header in text, (path, header)
    if https:
        assert "Strict-Transport-Security" in text
        assert "${TLS_IP}" in text
    else:
        assert "Strict-Transport-Security" not in text
        assert "${TLS_IP}" not in text
    # 大括号平衡、每条指令以分号或块结束。
    depth = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        depth += stripped.count("{") - stripped.count("}")
        assert depth >= 0, (path, line)
        if depth == 0 and not stripped.endswith((";", "{", "}")):
            raise AssertionError((path, line))
    assert depth == 0, path
    # 只允许 nginx 自身变量与 ${TLS_IP}，避免 envsubst 误替换。
    variables = set(re.findall(r"\$(\w+|\{\w+\})", text))
    assert variables <= {"http_host", "remote_addr", "scheme", "{TLS_IP}"}, variables


def test_nginx_https_template_headers_and_tls_ip():
    check_nginx_template(DEPLOY / "nginx-https.conf.template", https=True)


def test_nginx_http_template_headers_no_hsts():
    check_nginx_template(DEPLOY / "nginx-http.conf.template", https=False)


def test_nginx_csp_allows_only_same_origin():
    text = read(DEPLOY / "nginx-https.conf.template")
    csp = re.search(r'Content-Security-Policy "([^"]+)"', text).group(1)
    assert "script-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    # stage23-1 已把 live/ 全部行内样式迁走，style-src 不再放行 'unsafe-inline'。
    assert "style-src 'self'" in csp
    assert "'unsafe-inline'" not in csp


# ---------- .env.example / 续期 / systemd ----------

def test_env_example_parameterized_no_old_ip():
    text = read(DEPLOY / ".env.example")
    assert OLD_IP not in text
    assert "PUBLIC_HOST=8.152.206.86" in text
    assert "TLS_IP=8.152.206.86" in text
    assert "GATEWAY_CONFIG=./nginx-https.conf.template" in text
    assert "MT_PUBLIC_ORIGIN=https://8.152.206.86:5488" in text


def load_renew_module():
    spec = importlib.util.spec_from_file_location(
        "renew_certificate", DEPLOY / "renew_certificate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_renew_certificate_image_pinned(monkeypatch):
    module = load_renew_module()
    assert module.CERTBOT_IMAGE == "certbot/certbot:v5.10.0"
    assert ":latest" not in read(DEPLOY / "renew_certificate.py")
    assert OLD_IP not in read(DEPLOY / "renew_certificate.py")
    monkeypatch.setenv("TLS_IP", "8.152.206.86")
    assert module.resolve_tls_ip() == "8.152.206.86"
    assert module.resolve_tls_ip("1.2.3.4") == "1.2.3.4"
    monkeypatch.delenv("TLS_IP")
    monkeypatch.setenv("PUBLIC_HOST", "8.152.206.86")
    assert module.resolve_tls_ip() == "8.152.206.86"


def test_renew_certificate_requires_address(tmp_path):
    module = load_renew_module()
    with pytest.raises(ValueError, match="TLS_IP"):
        module.renew(tmp_path, None)


def test_certificate_service_uses_tls_ip():
    text = read(DEPLOY / "model-platform-certificate.service")
    assert OLD_IP not in text
    assert "EnvironmentFile=-/srv/model-platform/current/deploy/server/.env" in text
    assert "--ip ${TLS_IP}" in text


def test_backup_timer_daily_0300():
    timer = read(DEPLOY / "model-platform-backup.timer")
    assert "OnCalendar=*-*-* 03:00:00" in timer
    assert "Persistent=true" in timer
    assert "Unit=model-platform-backup.service" in timer
    service = read(DEPLOY / "model-platform-backup.service")
    assert "backup.sh /srv/model-platform" in service


# ---------- backup.sh / restore.sh ----------

def test_backup_script_dumps_application_database():
    text = read(DEPLOY / "backup.sh")
    assert 'pg_dump -U "${APP_USER}" -Fc -d "${APP_DATABASE}"' in text
    assert 'APP_DATABASE="model_platform"' in text
    # 旧 bug：容器内 ${POSTGRES_USER:-model_platform} 展开成 postgres，
    # 实际备份的是 postgres 维护库而不是应用库（注释里提及旧写法除外）。
    assert 'pg_dump -U "${POSTGRES_USER' not in text
    assert "sh -c 'pg_dump" not in text
    assert "tables.txt" in text and "backup.json" in text
    result = run_bash(f"bash -n {DEPLOY / 'backup.sh'}")
    assert result.returncode == 0, result.stderr
    result = run_bash(f"bash {DEPLOY / 'backup.sh'} --help")
    assert result.returncode == 0 and "用法" in result.stdout


def test_restore_script_argument_validation():
    result = run_bash(f"bash -n {DEPLOY / 'restore.sh'}")
    assert result.returncode == 0, result.stderr
    result = run_bash(f"bash {DEPLOY / 'restore.sh'} --help")
    assert result.returncode == 0 and "用法" in result.stdout
    result = run_bash(f"bash {DEPLOY / 'restore.sh'}")
    assert result.returncode != 0
    result = run_bash(f"bash {DEPLOY / 'restore.sh'} --backup-dir /definitely/not/here --yes")
    assert result.returncode != 0


def test_restore_verify_counts(tmp_path):
    manifest = tmp_path / "tables.txt"
    manifest.write_text("users 3\njobs 0\n", encoding="utf-8")
    actual = tmp_path / "actual.txt"
    actual.write_text("users 3\njobs 0\n", encoding="utf-8")
    script = (
        f"source {DEPLOY / 'restore.sh'}; "
        f"if verify_counts {manifest} {actual}; then echo PASS; else echo FAIL; fi"
    )
    assert run_bash(script).stdout.strip() == "PASS"
    actual.write_text("users 2\njobs 0\n", encoding="utf-8")
    assert run_bash(script).stdout.strip() == "FAIL"
    actual.write_text("users 3\n", encoding="utf-8")
    assert run_bash(script).stdout.strip() == "FAIL"
    actual.write_text("users 3\njobs 0\nextra 1\n", encoding="utf-8")
    assert run_bash(script).stdout.strip() == "FAIL"


def test_restore_verify_storage(tmp_path):
    manifest = tmp_path / "backup.json"
    manifest.write_text('{\n  "storage_files": 5\n}\n', encoding="utf-8")
    script = (
        f"source {DEPLOY / 'restore.sh'}; "
        f"if verify_storage {manifest} 5; then echo PASS; else echo FAIL; fi"
    )
    assert run_bash(script).stdout.strip() == "PASS"
    script = (
        f"source {DEPLOY / 'restore.sh'}; "
        f"if verify_storage {manifest} 4; then echo PASS; else echo FAIL; fi"
    )
    assert run_bash(script).stdout.strip() == "FAIL"


def test_restore_manifest_sha_extraction(tmp_path):
    # 回归：grep 提取摘要时不能用 [0-9a-f]*，否则 "dump_sha256" 里的
    # 十六进制字母（d/a/f/256）会被当成摘要片段，导致校验恒失败。
    manifest = tmp_path / "backup.json"
    sha = "f03e0d0bdb1db497ad29ed581efd1bdae6b93f61bc0e8ca499721771618ee187"
    manifest.write_text(f'{{\n  "dump_sha256": "{sha}"\n}}\n', encoding="utf-8")
    script = (
        f"grep -oE '\"dump_sha256\": \"[0-9a-f]{{64}}\"' {manifest} "
        f"| grep -oE '[0-9a-f]{{64}}'"
    )
    assert run_bash(script).stdout.strip() == sha


def test_no_old_ip_in_live_deploy_files():
    live = ["compose.yaml", "nginx-https.conf.template", "nginx-http.conf.template",
            ".env.example", "renew_certificate.py", "backup.sh", "restore.sh",
            "model-platform-certificate.service", "model-platform-certificate.timer",
            "model-platform-backup.service", "model-platform-backup.timer"]
    offenders = [name for name in live if OLD_IP in read(DEPLOY / name)]
    assert offenders == []
    assert not (DEPLOY / "nginx-https.conf").exists()
    assert not (DEPLOY / "nginx-http.conf").exists()
