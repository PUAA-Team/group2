"""监控采样、设备授权、组预算、存储账目与人工核查。"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0008_govern"
down_revision = "0007_results"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("models", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("datasets", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("executions", sa.Column("group_id", sa.String(40), nullable=True))
    op.create_index("ix_executions_group_id", "executions", ["group_id"])
    op.create_table("node_samples", sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("node_id", sa.String(40), sa.ForeignKey("compute_nodes.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False), sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("node_id", "seq"))
    for field in ("node_id", "created_at"):
        op.create_index("ix_node_samples_" + field, "node_samples", [field])
    for table, parent in (("device_policies", "compute_devices"), ("group_budgets", "user_groups")):
        op.create_table(table, sa.Column("id", sa.String(40), sa.ForeignKey(parent + ".id"), primary_key=True),
            sa.Column("value", sa.JSON(), nullable=False), sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_" + table + "_created_at", table, ["created_at"])
    op.create_table("stored_objects", sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("workspace_id", sa.String(40), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("owner_id", sa.String(40), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("group_id", sa.String(40), sa.ForeignKey("user_groups.id"), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False), sa.Column("object_id", sa.String(40), nullable=False),
        sa.Column("storage_key", sa.String(200), nullable=False, unique=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    for field in ("workspace_id", "owner_id", "group_id", "created_at"):
        op.create_index("ix_stored_objects_" + field, "stored_objects", [field])
    op.create_table("execution_reviews", sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("execution_id", sa.String(40), sa.ForeignKey("executions.id"), nullable=False, unique=True),
        sa.Column("actor_id", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False), sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_execution_reviews_created_at", "execution_reviews", ["created_at"])
    connection = op.get_bind()
    # 只恢复可追溯的创建人，不用当前成员关系推测历史计入组。
    connection.execute(sa.text("""INSERT INTO stored_objects
        (id,workspace_id,owner_id,group_id,kind,object_id,storage_key,size_bytes,created_at)
        SELECT v.id,d.workspace_id,(SELECT a.actor_id FROM audit_events a
        WHERE a.target_id=v.id AND a.action='dataset_versions.create'
        ORDER BY a.created_at,a.id LIMIT 1),NULL,'dataset',v.id,v.storage_key,v.size_bytes,v.created_at
        FROM dataset_versions v JOIN datasets d ON d.id=v.dataset_id"""))
    connection.execute(sa.text("""INSERT INTO stored_objects
        (id,workspace_id,owner_id,group_id,kind,object_id,storage_key,size_bytes,created_at)
        SELECT 'artifact:'||id,workspace_id,created_by,NULL,'artifact',id,artifact_key,artifact_bytes,created_at
        FROM jobs WHERE artifact_key IS NOT NULL AND artifact_bytes IS NOT NULL"""))
    for row in connection.execute(sa.text("SELECT id,workspace_id,created_by,candidates,created_at FROM data_operations")).mappings():
        candidates = json.loads(row["candidates"]) if isinstance(row["candidates"], str) else row["candidates"]
        for index, candidate in enumerate(candidates or []):
            connection.execute(sa.text("""INSERT INTO stored_objects
                (id,workspace_id,owner_id,group_id,kind,object_id,storage_key,size_bytes,created_at)
                VALUES (:id,:space,:owner,NULL,'candidate',:object,:key,:size,:created)"""), {
                "id": f"candidate:{row['id']}:{index}", "space": row["workspace_id"], "owner": row["created_by"],
                "object": row["id"], "key": candidate["storage_key"], "size": candidate["size_bytes"], "created": row["created_at"]})


def downgrade():
    for table in ("execution_reviews", "stored_objects", "group_budgets", "device_policies", "node_samples"):
        op.drop_table(table)
    op.drop_index("ix_executions_group_id", table_name="executions")
    op.drop_column("executions", "group_id")
    op.drop_column("datasets", "archived")
    op.drop_column("models", "archived")
