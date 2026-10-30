from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class Problem(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        self.status, self.code, self.message = status, code, message
        self.details = details or []


def response(request: Request, data, *, pagination=None):
    result = {"data": data, "request_id": request.state.request_id}
    if pagination is not None:
        result["pagination"] = pagination
    return result


def install_handlers(app):
    @app.exception_handler(Problem)
    async def problem_handler(request, exc):
        return JSONResponse(status_code=exc.status, content={"error": {
            "code": exc.code, "message": exc.message, "details": exc.details},
            "request_id": request.state.request_id})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        # 不输出 input、ctx 或完整异常，避免密码等原始字段进入响应。
        details = [{"loc": list(item["loc"]), "type": item["type"],
                    "message": item["msg"]} for item in exc.errors()]
        return await problem_handler(request, Problem(422, "VALIDATION_ERROR", "输入校验失败", details))

    @app.exception_handler(HTTPException)
    async def http_handler(request, exc):
        return await problem_handler(request, Problem(exc.status_code, "INVALID_REQUEST", "请求路径或方法不受支持"))
