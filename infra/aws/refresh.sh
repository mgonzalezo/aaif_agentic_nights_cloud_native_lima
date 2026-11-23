#!/usr/bin/env bash
# Run ON THE INSTANCE (as root, through SSM): pull the latest commit of REPO_REF into /opt/bestiary and,
# with --apply, re-run bootstrap (idempotent, about a minute when nothing big changed: images are cached,
# models are already on disk). The GitHub token is read from SSM and lives only in the environment of
# the git process: not in argv, not in .git/config, not in the log.
#
#   sudo bash /opt/bestiary/infra/aws/refresh.sh --apply
set -Eeuo pipefail
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}" HOME=/root
set -a; . /etc/bestiary.env; set +a   # REPO_REF, GITHUB_TOKEN_PARAM, ... (non-secret, written by user data)

TOKEN=$(aws ssm get-parameter --name "$GITHUB_TOKEN_PARAM" --with-decryption --query Parameter.Value --output text)
ASK=$(mktemp /run/bestiary-askpass.XXXXXX)
printf '#!/bin/sh\ncase "$1" in Username*) echo x-access-token ;; *) printf "%%s\\n" "$BESTIARY_GIT_TOKEN" ;; esac\n' > "$ASK"
chmod 700 "$ASK"
GIT_TERMINAL_PROMPT=0 GIT_ASKPASS="$ASK" BESTIARY_GIT_TOKEN="$TOKEN" git -c credential.helper= -C /opt/bestiary fetch --quiet origin "$REPO_REF"
rm -f "$ASK"; unset TOKEN
git -C /opt/bestiary reset --hard --quiet FETCH_HEAD
git -C /opt/bestiary log --oneline -1

if [[ "${1:-}" == "--apply" ]]; then
  echo "[$(date -u +%FT%TZ)] refresh: starting bootstrap" >> /var/log/bestiary-bootstrap.log
  bash /opt/bestiary/infra/aws/bootstrap.sh
fi
