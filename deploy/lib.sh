# shellcheck shell=bash disable=SC2034
# Settings and helpers shared by the deploy scripts. They source it; you do not run it.
# Modelled on the Akamai Hack Midwest starter kit (github.com/akamai-developers/akamai-workshop-hackmidwest):
# same region, same linode-cli calls. Every resource is labelled tripwright-*.

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO" || exit 1

REGION=us-sea
CLUSTER=us-sea-1  # the Object Storage cluster in Seattle
OBJ_ENDPOINT=us-sea-1.linodeobjects.com
DB_LABEL=tripwright-db
DB_TYPE=g6-nanode-1
DB_ENGINE=postgresql/17
KEY_LABEL=tripwright-key
FIREWALL_LABEL=tripwright-fw
LINODE_LABEL=tripwright-app
LINODE_TYPE=g6-standard-4  # 4 vCPU / 8 GB: room for the API plus four parallel Chromium sessions
LINODE_IMAGE=linode/ubuntu24.04
APP_DIR=/opt/tripwright
SSH_KEY=${SSH_KEY:-$HOME/.ssh/id_ed25519}

if [[ ! -f .env ]]; then
  echo "No .env file. Run: cp .env.example .env"
  exit 1
fi
if ! command -v linode-cli >/dev/null; then
  echo "linode-cli not found. Run: pip install linode-cli && linode-cli configure"
  exit 1
fi

# get_env KEY: print KEY's value from .env. Prints nothing if KEY is missing.
get_env() {
  { grep "^$1=" .env || true; } | tail -n 1 | tr -d '\r' | cut -d= -f2- | sed -e "s/^[\"']//" -e "s/[\"']\$//"
}

# set_env KEY VALUE: replace the KEY= line in .env, or add one at the end.
set_env() {
  local tmp
  tmp=$(mktemp)
  KEY="$1" VALUE="$2" awk '
    BEGIN { key = ENVIRON["KEY"]; line = key "=" ENVIRON["VALUE"] }
    index($0, key "=") == 1 { if (!done) print line; done = 1; next }
    { print }
    END { if (!done) print line }
  ' .env > "$tmp" && cat "$tmp" > .env
  rm -f "$tmp"
}

my_ip() {
  curl -s --max-time 10 https://api.ipify.org || curl -s --max-time 10 https://ipv4.icanhazip.com
}

# bucket_name: tripwright- plus 8 characters derived from your account. Bucket names are
# shared by every customer in a region, so a fixed name would be taken.
bucket_name() {
  local euuid
  euuid=$(linode-cli account view --text --no-headers --format euuid)
  echo "tripwright-$(python3 -c 'import hashlib, sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:8])' "$euuid")"
}

db_id() {
  linode-cli databases postgresql-list --label "$DB_LABEL" --text --no-headers --format id
}

# wait_for SECONDS WHAT COMMAND...: run COMMAND every 5 seconds until it succeeds.
wait_for() {
  local limit=$1 what=$2 waited=0
  shift 2
  until "$@" >/dev/null 2>&1; do
    if (( waited >= limit )); then
      echo "Gave up after $limit seconds waiting for $what."
      return 1
    fi
    sleep 5
    waited=$((waited + 5))
  done
}
