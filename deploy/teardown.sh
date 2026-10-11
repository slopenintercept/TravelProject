#!/usr/bin/env bash
# Delete every Akamai resource the deploy scripts created, so nothing keeps billing.
# This permanently deletes the database and every evidence snapshot in the bucket.
#   bash deploy/teardown.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"

read -r -p "Delete the Linode, firewall, database, bucket and access key labelled tripwright-*? Type yes: " answer
[[ $answer == yes ]] || { echo "Nothing deleted."; exit 0; }

linode_id=$(linode-cli linodes list --label "$LINODE_LABEL" --text --no-headers --format id)
[[ -z $linode_id ]] || { linode-cli linodes delete "$linode_id"; echo "Deleted Linode $LINODE_LABEL."; }

fw_id=$(linode-cli firewalls list --label "$FIREWALL_LABEL" --text --no-headers --format id)
[[ -z $fw_id ]] || { linode-cli firewalls delete "$fw_id"; echo "Deleted firewall $FIREWALL_LABEL."; }

id=$(db_id)
[[ -z $id ]] || { linode-cli databases postgresql-delete "$id"; echo "Deleted database $DB_LABEL."; }

bucket=$(get_env OBJ_BUCKET)
if [[ $bucket == tripwright-* ]]; then
  linode-cli obj rb --recursive "$bucket" --cluster "$CLUSTER" && echo "Deleted bucket $bucket."
fi
key_id=$(get_env OBJ_KEY_ID)
[[ -z $key_id ]] || { linode-cli object-storage keys-delete "$key_id"; echo "Revoked access key $KEY_LABEL."; }

for key in OBJ_ENDPOINT OBJ_BUCKET OBJ_ACCESS_KEY OBJ_SECRET_KEY OBJ_KEY_ID DATABASE_URL; do set_env "$key" ""; done
echo "Cleared the Akamai settings in .env.hosted."
