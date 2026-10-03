#!/usr/bin/env bash
# Run as root. Pull an immutable image; preserve data; rollback image AND schema on failure.
set -Eeuo pipefail
umask 077
publisher_image=${1:?Usage: pull-publisher.sh ghcr.io/owner/image@sha256:digest}
[[ "$publisher_image" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]] || { echo 'Expected a GHCR digest-pinned image' >&2; exit 2; }
[[ $(id -u) == 0 ]] || { echo 'Run with sudo' >&2; exit 2; }
publisher_release=$(cd -- "$(dirname -- "$0")" && pwd)
publisher_data=${PUBLISHER_DATA_PATH:-/opt/wechat-publisher/data}
publisher_backups=${PUBLISHER_BACKUP_PATH:-/opt/wechat-publisher/backups}
publisher_project=${PUBLISHER_COMPOSE_PROJECT:-deploy}
exec 9>/opt/wechat-publisher/deploy.lock
flock -n 9 || { echo 'A deployment is already running' >&2; exit 1; }
compose=(docker compose --project-name "$publisher_project" -f "$publisher_release/docker-compose.tencent.yml")
export PUBLISHER_IMAGE="$publisher_image"
"${compose[@]}" config --quiet
# Pull before stopping the working service. Registry authentication is configured on the server.
"${compose[@]}" pull publisher
publisher_container=$(docker ps -aq --filter "label=com.docker.compose.project=$publisher_project" --filter 'label=com.docker.compose.service=publisher')
[[ $(wc -w <<< "$publisher_container") -le 1 ]] || { echo 'Multiple Publisher containers; resolve before deploying' >&2; exit 1; }
publisher_previous=''
if [[ -n "$publisher_container" ]]; then publisher_previous=$(docker inspect --format '{{.Image}}' "$publisher_container"); fi
publisher_backup=''
publisher_changed=false
rollback() {
    result=$?
    trap - ERR INT TERM
    if [[ "$publisher_changed" == true ]]; then
        echo 'Deployment failed; restoring the pre-deployment database and image' >&2
        "${compose[@]}" stop publisher || true
        if [[ -n "$publisher_backup" ]]; then
            publisher_restore=$(mktemp -d /opt/wechat-publisher/restore.XXXXXX)
            tar -xzf "$publisher_backup" -C "$publisher_restore"
            rm -f "$publisher_data/publisher.db-wal" "$publisher_data/publisher.db-shm"
            install -o 10001 -g 10001 -m 600 "$publisher_restore/publisher.db" "$publisher_data/publisher.db"
            if [[ -d "$publisher_restore/assets" ]]; then cp -a "$publisher_restore/assets/." "$publisher_data/assets/"; chown -R 10001:10001 "$publisher_data/assets"; fi
            rm -rf -- "$publisher_restore"
        fi
        if [[ -n "$publisher_previous" ]]; then
            PUBLISHER_IMAGE="$publisher_previous" "${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 120 publisher || echo 'Automatic rollback failed; inspect the service' >&2
        fi
    fi
    exit "${result:-1}"
}
trap rollback ERR INT TERM
if [[ -n "$publisher_container" ]]; then docker stop "$publisher_container"; fi
publisher_changed=true
if [[ -f "$publisher_data/publisher.db" ]]; then
    publisher_backup=$(python3 "$publisher_release/backup.py" --data "$publisher_data" --output "$publisher_backups")
    echo "Pre-deployment backup: $publisher_backup"
else
    install -d -o 10001 -g 10001 -m 700 "$publisher_data"
fi
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 120 publisher
publisher_id=$("${compose[@]}" ps -q publisher)
[[ "$(docker inspect --format '{{.State.Health.Status}}' "$publisher_id")" == healthy ]]
# Preserve exact image/Compose/backup provenance for operational rollback.
python3 - "$publisher_image" "$publisher_previous" "$publisher_backup" "$publisher_release" <<'PY'
import json, sys, pathlib, datetime
record=dict(zip(('image','previous_image','backup','release'),sys.argv[1:]))
record['deployed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
p=pathlib.Path('/opt/wechat-publisher/current-release.json')
temp=p.with_suffix('.tmp'); temp.write_text(json.dumps(record,indent=2)); temp.chmod(0o600); temp.replace(p)
PY
trap - ERR INT TERM
echo "Publisher healthy: $publisher_image"
