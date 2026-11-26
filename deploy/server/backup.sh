#!/usr/bin/env bash
# 每日备份：PostgreSQL 应用库 model_platform（custom 格式）+ runtime/storage，
# 并写出清单 backup.json / tables.txt，供 restore.sh 校验表记录数。
#
# 注意：db 容器内 POSTGRES_USER/POSTGRES_DB 是 postgres（维护库），
# 应用库是 model_platform；旧脚本用 ${POSTGRES_USER:-model_platform}
# 在容器内展开后实际备份的是 postgres 维护库，本轮已修正为显式
# -U postgres -d model_platform（容器内本地连接为 trust 认证）。
set -euo pipefail

APP_DATABASE="model_platform"
APP_USER="postgres"

usage() {
  echo "用法：backup.sh [--root <部署根目录>] [--help]"
  echo "默认根目录：/srv/model-platform；由 systemd 定时任务每日 03:00 调用。"
}

compose() {
  docker compose --env-file "${DEPLOY_DIR}/.env" -f "${DEPLOY_DIR}/compose.yaml" "$@"
}

# 把 public schema 各表的精确行数写入 <备份目录>/tables.txt（每行“表名 行数”）。
write_table_counts() {
  local backup_dir="$1" tables table count
  tables="$(compose exec -T db psql -U "${APP_USER}" -d "${APP_DATABASE}" -At \
    -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")"
  : > "${backup_dir}/tables.txt"
  while IFS= read -r table; do
    [ -n "$table" ] || continue
    count="$(compose exec -T db psql -U "${APP_USER}" -d "${APP_DATABASE}" -At \
      -c "SELECT count(*) FROM \"${table}\"")"
    printf '%s %s\n' "$table" "$count" >> "${backup_dir}/tables.txt"
  done <<< "$tables"
  [ -s "${backup_dir}/tables.txt" ] || { echo "表清单为空，备份中止" >&2; return 1; }
}

# 写出清单 backup.json：创建时间、数据库、dump 摘要与大小、存储文件数与字节数。
# 值均为受控内容（时间戳、固定库名、十六进制摘要、整数），直接拼接 JSON 安全。
write_manifest() {
  local backup_dir="$1" dump_sha dump_bytes storage_files storage_bytes
  dump_sha="$(sha256sum "${backup_dir}/database.dump" | awk '{print $1}')"
  dump_bytes="$(stat -c %s "${backup_dir}/database.dump")"
  if [ -d "${ROOT}/runtime/storage" ]; then
    storage_files="$(find "${ROOT}/runtime/storage" -type f | wc -l)"
    storage_bytes="$(du -sb "${ROOT}/runtime/storage" | awk '{print $1}')"
  else
    storage_files=0
    storage_bytes=0
  fi
  printf '{\n  "created_at": "%s",\n  "database": "%s",\n  "dump_sha256": "%s",\n  "dump_bytes": %s,\n  "storage_files": %s,\n  "storage_bytes": %s\n}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${APP_DATABASE}" "${dump_sha}" "${dump_bytes}" \
    "${storage_files}" "${storage_bytes}" > "${backup_dir}/backup.json"
}

main() {
  local root="/srv/model-platform"
  while [ $# -gt 0 ]; do
    case "$1" in
      --root) root="${2:-}"; shift 2 ;;
      --help|-h) usage; return 0 ;;
      --*) echo "未知参数：$1（用 --help 查看用法）" >&2; return 1 ;;
      *) # 兼容旧调用方式：第一个位置参数仍可作根目录。
        root="$1"; shift ;;
    esac
  done
  ROOT="$root"
  DEPLOY_DIR="${ROOT}/current/deploy/server"
  BACKUP_DIR="${ROOT}/backups/$(date -u +%Y%m%dT%H%M%SZ)"
  [ -f "${DEPLOY_DIR}/compose.yaml" ] || { echo "找不到 ${DEPLOY_DIR}/compose.yaml" >&2; return 1; }
  [ -f "${DEPLOY_DIR}/.env" ] || { echo "找不到 ${DEPLOY_DIR}/.env" >&2; return 1; }

  mkdir -p "${BACKUP_DIR}"
  compose exec -T db pg_dump -U "${APP_USER}" -Fc -d "${APP_DATABASE}" \
    > "${BACKUP_DIR}/database.dump"
  [ -s "${BACKUP_DIR}/database.dump" ] || { echo "数据库备份为空" >&2; return 1; }
  write_table_counts "${BACKUP_DIR}"

  if [ -d "${ROOT}/runtime/storage" ]; then
    tar -czf "${BACKUP_DIR}/storage.tar.gz" -C "${ROOT}/runtime" storage
    tar -tzf "${BACKUP_DIR}/storage.tar.gz" >/dev/null || { echo "存储归档校验失败" >&2; return 1; }
  fi
  write_manifest "${BACKUP_DIR}"

  # 仅保留最近 7 份备份
  ls -dt "${ROOT}"/backups/* 2>/dev/null | tail -n +8 | xargs -r rm -rf
  echo "备份完成: ${BACKUP_DIR}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
