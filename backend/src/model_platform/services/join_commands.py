import shlex


def ps(value):
    return "'" + str(value).replace("'", "''") + "'"


def make_commands(payload, code, bundle_sha):
    endpoint = str(payload.controller_url).rstrip("/")
    bundle_url = endpoint + "/api/worker/v1/bundle?sha256=" + bundle_sha
    insecure = " --allow-http" if endpoint.startswith("http://") else ""
    if payload.platform == "windows":
        def command(secret):
            return (f"$d={ps(payload.state_dir)}; New-Item -ItemType Directory -Path $d -Force | Out-Null; "
                    f"$w=Join-Path $d 'worker.pyz'; Invoke-WebRequest -Uri {ps(bundle_url)} -OutFile $w; "
                    f"if ((Get-FileHash -LiteralPath $w -Algorithm SHA256).Hash.ToLower() -ne {ps(bundle_sha)}) {{ throw 'Worker SHA256 mismatch' }}; "
                    f"{ps(secret)} | & {ps(payload.training_python)} $w agent --controller {ps(endpoint)} --state-dir $d "
                    f"--trainer-python {ps(payload.training_python)} --join-code-stdin{insecure}")
    elif payload.platform == "linux":
        def command(secret):
            directory = '"${HOME}"/' + shlex.quote(payload.state_dir[2:]) if payload.state_dir.startswith("~/") else shlex.quote(payload.state_dir)
            return (f"worker_dir={directory}; mkdir -p \"$worker_dir\" && curl -fLsS {shlex.quote(bundle_url)} -o \"$worker_dir/worker.pyz\" && "
                    f"printf '%s  %s\\n' {shlex.quote(bundle_sha)} \"$worker_dir/worker.pyz\" | sha256sum -c - && "
                    f"printf '%s\\n' {shlex.quote(secret)} | {shlex.quote(payload.training_python)} \"$worker_dir/worker.pyz\" agent "
                    f"--controller {shlex.quote(endpoint)} --state-dir \"$worker_dir\" --trainer-python {shlex.quote(payload.training_python)} --join-code-stdin{insecure}")
    else:
        def command(secret):
            return (f"mkdir -p {shlex.quote(payload.state_dir)} && docker pull {shlex.quote(payload.image)} && printf '%s\\n' {shlex.quote(secret)} | docker run --rm -i --gpus all "
                    f"--mount {shlex.quote('type=bind,source=' + payload.state_dir + ',target=/state')} {shlex.quote(payload.image)} agent "
                    f"--controller {shlex.quote(endpoint)} --state-dir /state --join-code-stdin{insecure}")
    return {"command": command(code), "display_command": command("<一次性接入码>"), "bundle_sha256": bundle_sha,
            "platform": payload.platform, "controller_url": endpoint}
