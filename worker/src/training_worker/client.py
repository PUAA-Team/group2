import json
import urllib.error
import urllib.parse
import urllib.request


class WorkerError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status, self.code, self.details = status, code, details or []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, controller, key=None, allow_http=False):
        parsed = urllib.parse.urlsplit(controller)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("控制端地址无效")
        if parsed.scheme == "http" and not allow_http:
            raise ValueError("HTTP 开发接入需显式 --allow-http，正式部署使用 HTTPS")
        self.controller, self.key = controller.rstrip("/"), key
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, body=None, method=None, timeout=15):
        headers = {"Accept": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        content = json.dumps(body, ensure_ascii=False, allow_nan=False).encode() if body is not None else None
        if content is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.controller + "/api/worker/v1" + path, data=content, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                return json.load(response)["data"]
        except urllib.error.HTTPError as error:
            try:
                problem = json.load(error).get("error", {})
            except (ValueError, KeyError):
                problem = {}
            raise WorkerError(error.code, problem.get("code", "HTTP_ERROR"), problem.get("message", "控制端请求失败"), problem.get("details")) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise WorkerError(0, "NETWORK_ERROR", "连接暂时不可用") from None
