#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/srv/model-platform}"
DEPLOY_DIR="${ROOT}/current/deploy/server"
BACKUP_DIR="${ROOT}/backups/$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "${BACKUP_DIR}"
docker compose --env-file "${DEPLOY_DIR}/.env" -f "${DEPLOY_DIR}/compose.yaml" \
  exec -T db sh -c 'pg_dump -U "${POSTGRES_USER:-model_platform}" -Fc "${POSTGRES_DB:-model_platform}"' \
  > "${BACKUP_DIR}/database.dump"

if [ -d "${ROOT}/runtime/storage" ]; then
  tar -czf "${BACKUP_DIR}/storage.tar.gz" -C "${ROOT}/runtime" storage
fi

# 仅保留最近 7 份备份
ls -dt "${ROOT}/backups"/* 2>/dev/null | tail -n +8 | xargs -r rm -rf
echo "备份完成: ${BACKUP_DIR}"
