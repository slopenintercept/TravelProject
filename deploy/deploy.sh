#!/usr/bin/env bash
# Deploy Tripwright on an Akamai compute instance (Linode).
# Creates a Cloud Firewall and a Linode, waits for cloud-init to install Docker, lets the
# Linode into the database, copies the code and the settings over SSH, starts docker compose, and
# waits until http://<ip>:8000/api/health answers. Billable. Safe to run again.
#   bash deploy/deploy.sh
#   SSH_KEY=~/.ssh/other_key bash deploy/deploy.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"

if [[ ! -f $SSH_KEY.pub ]]; then
  echo "No SSH key at $SSH_KEY.pub. Make one with: ssh-keygen -t ed25519"
  exit 1
fi
ssh_opts=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o BatchMode=yes)

# 1. The Cloud Firewall: SSH and the app's port come in, everything else is dropped.
fw_id=$(linode-cli firewalls list --label "$FIREWALL_LABEL" --text --no-headers --format id)
if [[ -z $fw_id ]]; then
  fw_id=$(linode-cli firewalls create --label "$FIREWALL_LABEL" \
    --rules.inbound_policy DROP --rules.outbound_policy ACCEPT \
    --rules.inbound '[{"label": "ssh-and-app", "action": "ACCEPT", "protocol": "TCP", "ports": "22,8000", "addresses": {"ipv4": ["0.0.0.0/0"], "ipv6": ["::/0"]}}]' \
    --text --no-headers --format id)
  echo "Created firewall $FIREWALL_LABEL (id $fw_id)."
fi

# 2. The Linode. cloud-init installs Docker on first boot.
linode_id=$(linode-cli linodes list --label "$LINODE_LABEL" --text --no-headers --format id)
if [[ -z $linode_id ]]; then
  linode_id=$(linode-cli linodes create --label "$LINODE_LABEL" --region "$REGION" --type "$LINODE_TYPE" \
    --image "$LINODE_IMAGE" --root_pass "$(openssl rand -base64 32)" --authorized_keys "$(cat "$SSH_KEY.pub")" \
    --firewall_id "$fw_id" --metadata.user_data "$(base64 < deploy/cloud-init.yaml | tr -d '\n')" \
    --text --no-headers --format id)
  echo "Created Linode $LINODE_LABEL (id $linode_id)."
fi
ip=$(linode-cli linodes view "$linode_id" --text --no-headers --format ipv4)
ip=${ip%% *}

running() { [[ $(linode-cli linodes view "$linode_id" --text --no-headers --format status) == running ]]; }
wait_for 600 "$LINODE_LABEL to boot" running
echo "$LINODE_LABEL is running at $ip. Waiting for SSH and cloud-init."
wait_for 300 "SSH on $ip" ssh "${ssh_opts[@]}" "root@$ip" true
ssh "${ssh_opts[@]}" "root@$ip" cloud-init status --wait

# 3. Let the Linode into the database, keeping the addresses already on the allow list.
id=$(db_id)
if [[ -n $id && -n $(get_env DATABASE_URL) ]]; then
  allowed=$(linode-cli databases postgresql-view "$id" --text --no-headers --format allow_list | tr ',' ' ')
  if [[ " $allowed " != *" $ip/32 "* ]]; then
    args=()
    for address in $allowed "$ip/32"; do args+=(--allow_list "$address"); done
    linode-cli databases postgresql-update "$id" "${args[@]}" >/dev/null
    echo "Added $ip/32 to the allow list of $DB_LABEL."
  fi
fi

# 4. Copy the code and the settings, then build and start the container. backend/ and frontend/ are cleared
#    first, so a file deleted here does not stay behind on the server. The server's .env is the local one
#    with the hosted services' settings from .env.hosted. The build log stays on the Linode.
tar --exclude node_modules --exclude .venv --exclude dist --exclude __pycache__ -czf - \
  backend frontend Dockerfile compose.yaml .dockerignore \
  | ssh "${ssh_opts[@]}" "root@$ip" "rm -rf ${APP_DIR:?}/backend ${APP_DIR:?}/frontend && tar -xzf - -C $APP_DIR"
{ grep -vE '^(OBJ_[A-Z_]+|DATABASE_URL)=' .env; cat "$HOSTED_ENV"; } \
  | ssh "${ssh_opts[@]}" "root@$ip" "umask 077 && cat > $APP_DIR/.env"
echo "Code and settings copied. Building and starting the container (the first build takes a few minutes)."
ssh "${ssh_opts[@]}" "root@$ip" "cd $APP_DIR && { docker compose up -d --build > deploy.log 2>&1 || { tail -n 30 deploy.log; exit 1; }; }"

# 5. Wait for the app to answer.
healthy() { curl -sf --max-time 5 "http://$ip:8000/api/health"; }
wait_for 600 "http://$ip:8000/api/health" healthy

echo
curl -s "http://$ip:8000/api/health" | python3 -m json.tool
echo
echo "Tripwright is up: http://$ip:8000"
echo "SSH in with: ssh root@$ip    Logs: cd $APP_DIR && docker compose logs -f app"
