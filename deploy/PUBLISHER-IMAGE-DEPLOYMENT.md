# Publisher V2 image deployment

The existing server uses `/publisher/`, port 8088, the `stocklab_application` network and the Compose project `deploy`. Data stays at `/opt/wechat-publisher/data`; secrets stay at `/opt/wechat-publisher/secrets/publisher.env`. The Tencent Compose now uses an image, without source builds or host-mounted templates/config. Templates and configuration come from the matching image.

## One-time setup

1. Merge the V2 PR to main. `Build Publisher image` tests and publishes `ghcr.io/mattxiaoxuesheng/workflow-hub/wechat-publisher:sha-<full commit SHA>`. For existing main commits, run the image workflow manually.
2. In GHCR set the package to public, or authenticate **root's Docker client on the server** with a token limited to `read:packages`: `sudo docker login ghcr.io`. No registry token belongs in the application env file. Public repository visibility does not automatically make its GHCR package public.
3. Verify server Docker Compose supports `up --wait`; ensure `python3`, `flock`, Docker, existing external network and application env file are present. Verify the existing Publisher Compose project is `deploy` using container labels. If it differs, set `PUBLISHER_COMPOSE_PROJECT` when invoking the script manually or adjust the workflow for that server.
4. Configure environment `tencent-production` with secrets: `TENCENT_SSH_HOST`, `TENCENT_SSH_USER`, `TENCENT_SSH_PRIVATE_KEY`, `TENCENT_SSH_KNOWN_HOSTS`; optionally `TENCENT_SSH_PORT` (default 22). Copy the verified server host key from an already trusted connection. The deployment user needs noninteractive sudo for the deployment commands. Restrict SSH access according to your server policy. GitHub runners must be able to reach the SSH port.
5. Run `Deploy Publisher to Tencent` on main with the full SHA of the successfully built image. Deployment resolves its digest, sends only deployment files and makes the server pull the image. It never runs a source build on Tencent.

The script pulls before stopping the old service, stops writers, creates a SQLite/asset backup, starts the new image and waits for container health. On failure it restores the pre-migration database and restarts the previous local image. The image, backup, previous image and deployment directory are recorded in `/opt/wechat-publisher/current-release.json`. No `docker compose down -v` or data-directory deletion is used.

## Manual deployment

Copy `docker-compose.tencent.yml`, `backup.py`, `pull-publisher.sh` into a server release directory, then run:

```bash
sudo bash /opt/wechat-publisher/releases/<release>/pull-publisher.sh \
  ghcr.io/mattxiaoxuesheng/workflow-hub/wechat-publisher@sha256:<64-character-digest>
```

## Rollback after a successful deployment

Read `current-release.json` and schedule a maintenance window. Stop Publisher first. Restore `publisher.db` and assets from the recorded pre-deployment archive, remove SQLite WAL/SHM files and ensure UID/GID 10001 owns the restored files. Then set `PUBLISHER_IMAGE` to the recorded previous image and run the recorded Compose with `up -d --no-build --pull never --wait`. Restoring a pre-upgrade backup discards edits after that backup; back up current data before doing this. Image-only rollback across a schema change is not sufficient.

## Validation and actual state

The workflow validates local container health. After deployment verify the external HTTPS `/publisher/` route, login, autosave, a historical version, image upload and Android WebView. Real WeChat operations require AppID/AppSecret and an API IP whitelist; they are performed only on explicit article confirmation. Creation of deployment files is not evidence that production has been deployed. Neither Tencent secrets nor GHCR visibility are created automatically by this change.
