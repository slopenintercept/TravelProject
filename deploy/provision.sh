#!/usr/bin/env bash
# Create the Akamai data services and write their settings into .env.hosted:
#   - Object Storage bucket + a bucket-scoped access key (evidence snapshots)
#   - Managed PostgreSQL (trip state, traveler profile, tool-result cache)
# These are billable. Safe to run again: it reuses whatever already exists.
#   bash deploy/provision.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"

# 1. The bucket. linode-cli's obj plugin makes itself an access key with no region, which the API
#    answers with a 500, so it is handed a temporary key that is deleted when this script ends.
read -r boot_id LINODE_CLI_OBJ_ACCESS_KEY LINODE_CLI_OBJ_SECRET_KEY <<<"$(linode-cli object-storage keys-create \
  --label tripwright-bootstrap --regions "$REGION" --text --no-headers --format id,access_key,secret_key)"
export LINODE_CLI_OBJ_ACCESS_KEY LINODE_CLI_OBJ_SECRET_KEY
trap 'linode-cli object-storage keys-delete "$boot_id" >/dev/null' EXIT

bucket=$(get_env OBJ_BUCKET)
[[ $bucket == tripwright-* ]] || bucket=$(bucket_name)
if ! linode-cli obj ls "$bucket" --cluster "$CLUSTER" >/dev/null 2>&1; then
  linode-cli obj mb "$bucket" --cluster "$CLUSTER"
  echo "Created bucket $bucket."
fi

# 2. An access key limited to that bucket. The secret is shown only once, so it goes straight into .env.hosted.
if [[ -z $(get_env OBJ_KEY_ID) || $(get_env OBJ_BUCKET) != "$bucket" ]]; then
  read -r key_id access secret <<<"$(linode-cli object-storage keys-create --label "$KEY_LABEL" \
    --bucket_access "[{\"region\": \"$REGION\", \"bucket_name\": \"$bucket\", \"permissions\": \"read_write\"}]" \
    --text --no-headers --format id,access_key,secret_key)"
  set_env OBJ_ENDPOINT "$OBJ_ENDPOINT"
  set_env OBJ_BUCKET "$bucket"
  set_env OBJ_ACCESS_KEY "$access"
  set_env OBJ_SECRET_KEY "$secret"
  set_env OBJ_KEY_ID "$key_id"
  echo "Created access key $KEY_LABEL and wrote OBJ_* to .env.hosted."
fi

# 3. The database. Only this machine is on the allow list until deploy.sh adds the Linode.
id=$(db_id)
if [[ -z $id ]]; then
  ip=$(my_ip)
  [[ -n $ip ]] || { echo "Could not find this machine's public IP for the database allow list."; exit 1; }
  linode-cli databases postgresql-create --label "$DB_LABEL" --region "$REGION" --type "$DB_TYPE" \
    --engine "$DB_ENGINE" --cluster_size 1 --allow_list "$ip/32" \
    --text --format id,label,region,type,engine,status
  id=$(db_id)
  echo "Created database $DB_LABEL. It takes 10 to 15 minutes to become active."
fi

active() { [[ $(linode-cli databases postgresql-view "$id" --text --no-headers --format status) == active ]]; }
echo "Waiting for $DB_LABEL to become active."
wait_for 1500 "$DB_LABEL to become active" active

host=$(linode-cli databases postgresql-view "$id" --text --no-headers --format hosts.primary)
port=$(linode-cli databases postgresql-view "$id" --text --no-headers --format port)
read -r user password <<<"$(linode-cli databases postgresql-creds-view "$id" --text --no-headers --format username,password)"
password=$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$password")
# Managed Databases refuse unencrypted connections.
set_env DATABASE_URL "postgresql://$user:$password@$host:$port/defaultdb?sslmode=require"

echo
echo "Bucket:   $bucket at $OBJ_ENDPOINT"
echo "Database: $host:$port (DATABASE_URL written to .env.hosted)"
echo "Next: bash deploy/deploy.sh"
