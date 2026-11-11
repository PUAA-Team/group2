from ..database import aware, utcnow


def finish_call(call, status, result):
    call.status, call.result, call.completed_at = status, result, utcnow()
    call.elapsed_ms = max(0, round((call.completed_at - aware(call.created_at)).total_seconds() * 1000))
