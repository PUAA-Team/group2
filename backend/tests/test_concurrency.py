from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, BrokenBarrierError

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from model_platform.models import User
from conftest import create_user, login


def test_concurrent_disables_keep_one_active_admin(app, admin):
    owner = admin.get("/api/v1/auth/session").json()["data"]["user"]
    second = create_user(admin, account="other-admin", is_admin=True)
    barrier = Barrier(2)

    def synchronize_old_count(connection, cursor, statement, parameters, context, many):
        if "count(" in statement.lower() and "users.active" in statement.lower():
            # 放大先检查再更新的竞争窗口；加锁后第二个请求需等待第一个事务结束。
            try:
                barrier.wait(timeout=0.5)
            except BrokenBarrierError:
                pass

    with TestClient(app) as client_a, TestClient(app) as client_b:
        login(client_a)
        login(client_b, "other-admin")
        event.listen(app.state.engine, "after_cursor_execute", synchronize_old_count)
        try:
            def disable(client, user_id):
                return client.patch(f"/api/v1/admin/users/{user_id}", json={"active": False},
                                    headers={"If-Match": '"1"'}).status_code
            with ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(disable, client_a, owner["id"])
                b = pool.submit(disable, client_b, second["id"])
                statuses = [a.result(), b.result()]
        finally:
            event.remove(app.state.engine, "after_cursor_execute", synchronize_old_count)
    with app.state.sessions() as db:
        remaining = db.scalar(select(func.count()).select_from(User).where(User.active.is_(True), User.is_admin.is_(True)))
    assert remaining >= 1, statuses
    assert sorted(statuses) == [200, 409]
