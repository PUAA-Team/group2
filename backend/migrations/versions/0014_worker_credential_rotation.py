"""Worker 凭据轮换与已撤销节点防复活。

设计选择：新建独立节点 + 部分唯一索引（dev-plan 19B-1）。
已撤销旧节点原样保留（历史审计与关联执行仍指向旧节点 ID），
同一台机器重新接入时新建独立 ComputeNode；machine_id /
installation_id 的全局唯一约束改为仅对未撤销节点生效的部分
唯一索引，已撤销节点不再占唯一位。credential_digest 仍全局
唯一，每次注册/轮换都换发新的随机凭据，不复用。
ComputeDevice.hardware_id 同理由全局唯一改为 (node_id, hardware_id)
复合唯一，否则新节点按同一硬件标识重建设备行时会撞唯一约束。

SQLite 说明：0002 建表时唯一约束没有显式命名，inspector
返回 name=None，Alembic batch 也无法按名删除未命名约束，
所以 SQLite 路径用显式建表 + 复制数据 + 改名重建表；
PostgreSQL 的唯一约束有名（<表>_<列>_key），可按名删除。

降级注意：若库里已存在同一 machine_id 的新旧两个节点，
恢复全局唯一约束会失败，需先清理重复的已撤销节点记录。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '0014_worker_credential'
down_revision = '0013_model_storage'
branch_labels = None
depends_on = None

_NODE_COLUMNS = ("id, workspace_id, installation_id, machine_id, name, credential_digest,"
                 " approved, enabled, revoked, slots, heartbeat_seq, heartbeat_digest,"
                 " last_seen_at, last_inventory_at, probe_request_id, inventory,"
                 " active_executions, created_at, revision")
_DEVICE_COLUMNS = ("id, node_id, hardware_id, kind, name, memory_mb, present,"
                   " metrics, reserved_execution_id, created_at")


def _rebuild_compute_nodes_sqlite(partial):
    """SQLite 重建 compute_nodes：partial=True 为升级（加过期字段、去全局唯一），反之为降级。"""
    expiry = ", credential_expires_at DATETIME" if partial else ""
    uniques = "UNIQUE (credential_digest)" if partial else (
        "UNIQUE (credential_digest), UNIQUE (installation_id), UNIQUE (machine_id)")
    op.execute(f"""CREATE TABLE compute_nodes_new (
        id VARCHAR(40) NOT NULL, workspace_id VARCHAR(40) NOT NULL,
        installation_id VARCHAR(64) NOT NULL, machine_id VARCHAR(64) NOT NULL,
        name VARCHAR(100) NOT NULL, credential_digest VARCHAR(64) NOT NULL{expiry},
        approved BOOLEAN NOT NULL, enabled BOOLEAN NOT NULL, revoked BOOLEAN NOT NULL,
        slots INTEGER NOT NULL, heartbeat_seq INTEGER NOT NULL, heartbeat_digest VARCHAR(64),
        last_seen_at DATETIME, last_inventory_at DATETIME, probe_request_id VARCHAR(40),
        inventory JSON NOT NULL, active_executions JSON NOT NULL,
        created_at DATETIME NOT NULL, revision INTEGER NOT NULL,
        PRIMARY KEY (id), {uniques},
        FOREIGN KEY(workspace_id) REFERENCES workspaces (id))""")
    if partial:
        op.execute(f"INSERT INTO compute_nodes_new ({_NODE_COLUMNS}, credential_expires_at)"
                   f" SELECT {_NODE_COLUMNS}, NULL FROM compute_nodes")
    else:
        op.execute(f"INSERT INTO compute_nodes_new ({_NODE_COLUMNS}) SELECT {_NODE_COLUMNS} FROM compute_nodes")
    op.execute("DROP TABLE compute_nodes")
    op.execute("ALTER TABLE compute_nodes_new RENAME TO compute_nodes")
    op.execute("CREATE INDEX ix_compute_nodes_created_at ON compute_nodes (created_at)")
    op.execute("CREATE INDEX ix_compute_nodes_workspace_id ON compute_nodes (workspace_id)")


def _rebuild_compute_devices_sqlite(composite):
    """SQLite 重建 compute_devices：composite=True 为升级（复合唯一），反之为降级。"""
    uniques = "UNIQUE (reserved_execution_id), UNIQUE (node_id, hardware_id)" if composite else (
        "UNIQUE (reserved_execution_id), UNIQUE (hardware_id)")
    op.execute(f"""CREATE TABLE compute_devices_new (
        id VARCHAR(40) NOT NULL, node_id VARCHAR(40) NOT NULL,
        hardware_id VARCHAR(160) NOT NULL, kind VARCHAR(16) NOT NULL,
        name VARCHAR(160) NOT NULL, memory_mb INTEGER NOT NULL,
        present BOOLEAN NOT NULL, metrics JSON NOT NULL,
        reserved_execution_id VARCHAR(40), created_at DATETIME NOT NULL,
        PRIMARY KEY (id), {uniques},
        FOREIGN KEY(node_id) REFERENCES compute_nodes (id))""")
    op.execute(f"INSERT INTO compute_devices_new ({_DEVICE_COLUMNS}) SELECT {_DEVICE_COLUMNS} FROM compute_devices")
    op.execute("DROP TABLE compute_devices")
    op.execute("ALTER TABLE compute_devices_new RENAME TO compute_devices")
    op.execute("CREATE INDEX ix_compute_devices_created_at ON compute_devices (created_at)")
    op.execute("CREATE INDEX ix_compute_devices_node_id ON compute_devices (node_id)")


def _unique_name(table, columns):
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints(table):
        if list(constraint["column_names"]) == list(columns) and constraint["name"]:
            return constraint["name"]
    return None


def _partial_indexes():
    # 仅未撤销节点占唯一位；SQLite 布尔存 0/1，PostgreSQL 存 false。
    op.create_index("uq_compute_nodes_machine_id_active", "compute_nodes", ["machine_id"], unique=True,
                    postgresql_where=text("revoked = false"), sqlite_where=text("revoked = 0"))
    op.create_index("uq_compute_nodes_installation_id_active", "compute_nodes", ["installation_id"], unique=True,
                    postgresql_where=text("revoked = false"), sqlite_where=text("revoked = 0"))


def upgrade():
    if op.get_bind().dialect.name == "sqlite":
        _rebuild_compute_nodes_sqlite(partial=True)
        _rebuild_compute_devices_sqlite(composite=True)
        _partial_indexes()
        violations = list(op.get_bind().execute(text("PRAGMA foreign_key_check")))
        if violations:
            raise RuntimeError(f"迁移后外键校验失败：{violations}")
        return
    op.add_column("compute_nodes", sa.Column("credential_expires_at", sa.DateTime(timezone=True), nullable=True))
    for table, columns in (("compute_nodes", ["machine_id"]), ("compute_nodes", ["installation_id"]),
                           ("compute_devices", ["hardware_id"])):
        name = _unique_name(table, columns)
        if name:
            op.drop_constraint(name, table, type_="unique")
    op.create_unique_constraint("uq_compute_devices_node_hardware", "compute_devices", ["node_id", "hardware_id"])
    _partial_indexes()


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("uq_compute_nodes_installation_id_active", table_name="compute_nodes")
        op.drop_index("uq_compute_nodes_machine_id_active", table_name="compute_nodes")
        _rebuild_compute_devices_sqlite(composite=False)
        _rebuild_compute_nodes_sqlite(partial=False)
        return
    op.drop_index("uq_compute_nodes_installation_id_active", table_name="compute_nodes")
    op.drop_index("uq_compute_nodes_machine_id_active", table_name="compute_nodes")
    op.drop_constraint("uq_compute_devices_node_hardware", "compute_devices", type_="unique")
    op.create_unique_constraint("uq_compute_devices_hardware_id", "compute_devices", ["hardware_id"])
    op.create_unique_constraint("uq_compute_nodes_machine_id", "compute_nodes", ["machine_id"])
    op.create_unique_constraint("uq_compute_nodes_installation_id", "compute_nodes", ["installation_id"])
    op.drop_column("compute_nodes", "credential_expires_at")
