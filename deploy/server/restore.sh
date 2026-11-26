#!/usr/bin/env bash
# 从指定备份目录一键恢复 PostgreSQL 应用库 model_platform + runtime/storage，
# 并逐表校验行数、校验存储文件数；校验通过后才重启 api/operations。
# 恢复前先停 api/operations 避免写入；校验失败时服务保持停止，需人工检查。
# 用法：restore.sh --backup-dir <备份目录> [--root /srv/model-platform] [--yes] [--skip-verify]
# 旧格式备份（无 tables.txt）只能加 --skip-verify 恢复，不做行数校验。
set -euo pipefail

APP_DATABASE="model_platform"
APP_USER="postgres"

usage() {
  cat <<'EOF'
用法：restore.sh --backup-dir <备份目录> [--root <部署根目录>] [--yes] [--skip-verify]
  --backup-dir   备份目录（backup.sh 生成，含 database.dump、backup.json、tables.txt）
  --root         部署根目录，默认 /srv/model-platform
  --yes          跳过交互确认（非交互调用时必须加）
  --skip-verify  跳过表记录数与存储文件数校验（仅用于旧格式备份）
EOF
}

die() {
  echo "错误：$*" >&2
  exit 1
}

compose() {
  docker compose --env-file "${DEPLOY_DIR}/.env" -f "${DEPLOY_DIR}/compose.yaml" "$@"
}

# 按行比对“表名 行数”：缺表、多表、行数不一致都算失败并打印差异。
# 参数：<清单 tables.txt> <实际行数文件>，成功返回 0。
verify_counts() {
  local manifest="$1" actual="$2" failed=0 line table expected got
  while IFS=' ' read -r table expected _rest || [ -n "$table" ]; do
    [ -n "$table" ] || continue
    got="$(awk -v t="$table" '$1 == t {print $2}' "$actual")"
    if [ -z "$got" ]; then
      echo "缺少表：$table" >&2; failed=1
    elif [ "$got" != "$expected" ]; then
      echo "行数不一致：$table 清单=$expected 实际=$got" >&2; failed=1
    fi
  done < "$manifest"
  while IFS=' ' read -r table _count || [ -n "$table" ]; do
    [ -n "$table" ] || continue
    if ! grep -q "^${table} " "$manifest"; then
      echo "多出表：$table" >&2; failed=1
    fi
  done < "$actual"
  return "$failed"
}

# 比对存储文件数：清单 backup.json 里的 storage_files 与实际文件数。
# 参数：<清单 backup.json> <实际文件数>，成功返回 0。
verify_storage() {
  local manifest_json="$1" actual_files="$2" expected
  expected="$(grep -oE '"storage_files": [0-9]+' "$manifest_json" | grep -oE '[0-9]+')"
  [ -n "$expected" ] || { echo "清单里没有 storage_files" >&2; return 1; }
  if [ "$actual_files" != "$expected" ]; then
    echo "存储文件数不一致：清单=$expected 实际=$actual_files" >&2
    return 1
  fi
  return 0
}

# 确保应用角色与数据库存在（全新数据卷时 init-database.sh 未必已跑过）。
ensure_database() {
  compose exec -T db psql -U "${APP_USER}" -d postgres --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_password MT_DATABASE_PASSWORD
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='model_platform') THEN
    CREATE ROLE model_platform LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
  END IF;
END $$;
SQL
  if ! compose exec -T db psql -U "${APP_USER}" -d postgres -At \
      -c "SELECT 1 FROM pg_database WHERE datname='model_platform'" | grep -q 1; then
    compose exec -T db psql -U "${APP_USER}" -d postgres \
      -c "CREATE DATABASE model_platform OWNER model_platform"
  fi
}

# 查询 public schema 各表精确行数，写入指定文件（每行“表名 行数”）。
query_table_counts() {
  local out="$1" tables table count
  tables="$(compose exec -T db psql -U "${APP_USER}" -d "${APP_DATABASE}" -At \
    -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")"
  : > "$out"
  while IFS= read -r table; do
    [ -n "$table" ] || continue
    count="$(compose exec -T db psql -U "${APP_USER}" -d "${APP_DATABASE}" -At \
      -c "SELECT count(*) FROM \"${table}\"")"
    printf '%s %s\n' "$table" "$count" >> "$out"
  done <<< "$tables"
}

main() {
  local backup_dir="" root="/srv/model-platform" yes=0 skip_verify=0
  local deploy_dir expected_sha actual_sha answer actual_counts restored_files stamp
  while [ $# -gt 0 ]; do
    case "$1" in
      --backup-dir) backup_dir="${2:-}"; shift 2 ;;
      --root) root="${2:-}"; shift 2 ;;
      --yes) yes=1; shift ;;
      --skip-verify) skip_verify=1; shift ;;
      --help|-h) usage; return 0 ;;
      *) die "未知参数：$1（用 --help 查看用法）" ;;
    esac
  done
  [ -n "$backup_dir" ] || die "必须指定 --backup-dir"
  [ -d "$backup_dir" ] || die "备份目录不存在：$backup_dir"
  [ -f "$backup_dir/database.dump" ] || die "备份目录里没有 database.dump"
  [ -f "$backup_dir/backup.json" ] || die "备份目录里没有 backup.json（旧格式备份请先确认来源）"
  if [ "$skip_verify" -eq 0 ]; then
    [ -f "$backup_dir/tables.txt" ] || die "备份目录里没有 tables.txt（旧格式备份请加 --skip-verify）"
  fi
  ROOT="$root"
  DEPLOY_DIR="${ROOT}/current/deploy/server"
  [ -f "${DEPLOY_DIR}/compose.yaml" ] || die "找不到 ${DEPLOY_DIR}/compose.yaml，请确认 --root"
  [ -f "${DEPLOY_DIR}/.env" ] || die "找不到 ${DEPLOY_DIR}/.env"

  # 先校验 dump 摘要，损坏的备份不等停服务才发现。
  expected_sha="$(grep -oE '"dump_sha256": "[0-9a-f]{64}"' "$backup_dir/backup.json" | grep -oE '[0-9a-f]{64}')"
  actual_sha="$(sha256sum "$backup_dir/database.dump" | awk '{print $1}')"
  [ -n "$expected_sha" ] && [ "$expected_sha" = "$actual_sha" ] \
    || die "database.dump 摘要与清单不符，备份可能损坏"

  if [ "$yes" -ne 1 ]; then
    echo "将从 $backup_dir 恢复到 $root（数据库 ${APP_DATABASE} 与 runtime/storage）"
    echo "恢复会先停 api/operations，校验通过后才重启。继续吗？[y/N]"
    read -r answer || die "已取消"
    [ "$answer" = "y" ] || [ "$answer" = "Y" ] || die "已取消"
  fi

  compose stop api operations
  ensure_database
  # pg_restore 未指定文件名时读标准输入（PostgreSQL 17 文档）。
  compose exec -T db pg_restore -U "${APP_USER}" -d "${APP_DATABASE}" \
    --clean --if-exists --exit-on-error < "$backup_dir/database.dump"

  if [ -f "$backup_dir/storage.tar.gz" ]; then
    if [ -d "${ROOT}/runtime/storage" ]; then
      stamp="$(date -u +%Y%m%dT%H%M%SZ)"
      mv "${ROOT}/runtime/storage" "${ROOT}/runtime/storage.bak.${stamp}"
      echo "原 storage 已移走：runtime/storage.bak.${stamp}"
    fi
    mkdir -p "${ROOT}/runtime"
    tar -xzf "$backup_dir/storage.tar.gz" -C "${ROOT}/runtime"
  fi

  if [ "$skip_verify" -eq 0 ]; then
    actual_counts="$(mktemp)"
    trap 'rm -f "$actual_counts"' EXIT
    query_table_counts "$actual_counts"
    verify_counts "$backup_dir/tables.txt" "$actual_counts" \
      || die "表记录数校验未通过，服务保持停止，请人工检查"
    if [ -f "$backup_dir/storage.tar.gz" ]; then
      restored_files="$(find "${ROOT}/runtime/storage" -type f 2>/dev/null | wc -l)"
      verify_storage "$backup_dir/backup.json" "$restored_files" \
        || die "存储文件数校验未通过，服务保持停止，请人工检查"
    fi
    rm -f "$actual_counts"
    trap - EXIT
  fi

  compose up -d api operations
  compose ps
  echo "恢复完成并已校验：$backup_dir"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
