from sqlalchemy import select

from ..compute_models import ComputeDevice, ComputeNode
from ..database import aware, utcnow
from ..errors import Problem
from ..governance_models import DevicePolicy
from ..governance_schemas import DevicePolicyInput
from ..models import User, UserGroup
from .common import audit, commit, revision_update


def device_policy(db, device_id):
    row = db.get(DevicePolicy, device_id)
    return {**DevicePolicyInput(revision=0).model_dump(), **(row.value if row else {}),
            "revision": row.revision if row else 0}


def purpose_matches(purpose, job_kind):
    return purpose == "shared" or purpose == ("inference" if job_kind == "service" else "train_eval")


def node_is_online(node, settings, now=None):
    return bool(node.last_seen_at and ((now or utcnow()) - aware(node.last_seen_at)).total_seconds()
                <= settings.node_timeout_seconds)


def node_accepts_tasks(node, settings, now=None):
    return node.approved and node.enabled and not node.revoked and node_is_online(node, settings, now)


def device_fits(job, device, runtime):
    return (device.kind == job.device_kind and device.memory_mb >= job.min_memory_mb
            and (device.kind != "cuda" or runtime.get("cuda_available")))


def runtime_fits(job, runtime):
    return (job.snapshot.get("trainer_id") in runtime.get("trainers", ())
            and (job.snapshot.get("config", {}).get("inference") is None
                 or runtime.get("inference_contract_version", 0) >= 1))


def policy_allows(rule, actor):
    if not rule.get("enabled", True) or actor.id in rule.get("deny_users", ()) or actor.group_id in rule.get("deny_groups", ()):
        return False
    users, groups = rule.get("allow_users", ()), rule.get("allow_groups", ())
    return not (users or groups) or actor.id in users or actor.group_id in groups


def device_allowed(rule, actor, job_kind):
    return purpose_matches(rule.get("purpose", "shared"), job_kind) and policy_allows(rule, actor)


def configured_devices(db, workspace_id, actor, *, device_kind=None, node_id=None):
    query = (select(ComputeNode, ComputeDevice, DevicePolicy.value)
             .join(ComputeDevice, ComputeDevice.node_id == ComputeNode.id)
             .outerjoin(DevicePolicy, DevicePolicy.id == ComputeDevice.id)
             .where(ComputeNode.workspace_id == workspace_id, ComputeNode.approved.is_(True),
                    ComputeNode.revoked.is_(False), ComputeDevice.present.is_(True)))
    if device_kind is not None:
        query = query.where(ComputeDevice.kind == device_kind)
    if node_id is not None:
        query = query.where(ComputeNode.id == node_id)
    return [(node, device, (rule or {}).get("purpose", "shared"))
            for node, device, rule in db.execute(query) if policy_allows(rule or {}, actor)]


def save_device_policy(db, actor, node, device, payload):
    from .compute import lock_node

    lock_node(db, node)
    db.refresh(device)
    row = db.get(DevicePolicy, device.id, populate_existing=True)
    revision = row.revision if row else 0
    if payload.revision != revision:
        raise Problem(412, "REVISION_MISMATCH", "授权已更新，请重新读取")
    old_purpose = (row.value if row else {}).get("purpose", "shared")
    purpose = payload.purpose if "purpose" in payload.model_fields_set else old_purpose
    if purpose != old_purpose and device.reserved_execution_id:
        raise Problem(409, "DEVICE_PURPOSE_IN_USE", "设备仍有执行占用，释放后可修改用途")
    for kind, model in (("users", User), ("groups", UserGroup)):
        for identifier in set(getattr(payload, "allow_" + kind)) | set(getattr(payload, "deny_" + kind)):
            if db.get(model, identifier) is None:
                raise Problem(422, "INVALID_PRINCIPAL", "授权用户或用户组不存在")
    values = {**(row.value if row else {}), **payload.model_dump(exclude={"revision"}), "purpose": purpose}
    if row:
        revision_update(db, row, {"value": values}, payload.revision)
    else:
        db.add(DevicePolicy(id=device.id, value=values))
    audit(db, actor, "resources.device_policy.update", device.id, node.workspace_id)
    if purpose != old_purpose:
        audit(db, actor, f"resources.device_purpose.{old_purpose}.{purpose}", device.id, node.workspace_id)
    commit(db)
    return device_policy(db, device.id)
