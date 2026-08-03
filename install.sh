#!/bin/bash

# Set working directory to /opt
cd /opt 

# Deploy Timesketch
echo "Deploying Timesketch..."
curl -s -O https://raw.githubusercontent.com/google/timesketch/master/contrib/deploy_timesketch.sh
chmod 755 deploy_timesketch.sh

# --- FIX: Upstream deploy_timesketch.sh polls docker `.State.Health.Status` on
# timesketch-web, but the upstream timesketch compose file no longer defines a
# HEALTHCHECK for that service. The probe stays "starting" until the 300s
# timeout fires `FAIL`. Replace the docker-inspect probe with an HTTP probe
# through nginx, and shorten the timeout. The containers are fine — only the
# probe is broken upstream.
python3 - <<'PYFIX'
import pathlib, re
p = pathlib.Path("deploy_timesketch.sh")
s = p.read_text()
s = re.sub(r"^TIMEOUT=300", "TIMEOUT=120", s, count=1, flags=re.M)
s = re.sub(
    r"HEALTH_STATUS=\$\(docker inspect[^\n]*\)",
    "HEALTH_STATUS=$(curl -fsS -o /dev/null -w '%{http_code}' "
    "http://127.0.0.1/login/ 2>/dev/null "
    "| grep -qE '200|302' && echo healthy || echo starting)",
    s,
)
p.write_text(s)
PYFIX

./deploy_timesketch.sh <<EOF
Y
N
EOF

# Change directory to timesketch
cd timesketch 

# --- FIX: Disable EVTX message-string expansion that crashes psort ---
FORMATTER_FILE="/opt/timesketch/etc/timesketch/plaso_formatters.yaml"

if [ -f "$FORMATTER_FILE" ]; then
  echo "Patching Plaso EVTX formatter to avoid winevt_rc crash..."

  cp -a "$FORMATTER_FILE" "${FORMATTER_FILE}.bak"

  # Remove the custom helper that triggers winevt_rc
  sed -i '/^custom_helpers:/,/^message:/{
    /^custom_helpers:/d
    /identifier: '\''windows_eventlog_message'\''/d
    /output_attribute: '\''message_string'\''/d
  }' "$FORMATTER_FILE"

  # Remove the {message_string} line from message section
  sed -i "/^[[:space:]]*-[[:space:]]*'{message_string}'[[:space:]]*$/d" "$FORMATTER_FILE"

  echo "Formatter patched successfully."
else
  echo "WARNING: Formatter file not found at $FORMATTER_FILE"
fi
# --------------------------------------------------------------------

# Restart Timesketch worker so change takes effect
docker compose restart timesketch-worker

# Create Timesketch user
echo -e "${TIMESKETCH_PASSWORD}\n${TIMESKETCH_PASSWORD}" | \
  docker compose exec -T timesketch-web tsctl create-user "admin"

# Deploy OpenRelik
echo "Deploying OpenRelik..."
cd /opt 
curl -s -O https://raw.githubusercontent.com/openrelik/openrelik-deploy/main/docker/install.sh

# Run the installation script
# Upstream installer is interactive: it `read -rp`s for a release version
# (default 1 = latest stable) and reads OPENRELIK_ADMIN_PASSWORD from the env.
# Feed an empty line to accept the default; export the password for the child.
export OPENRELIK_ADMIN_PASSWORD
bash install.sh <<< ""

# Configure OpenRelik
echo "Configuring OpenRelik..."
cd /opt/openrelik 
chmod 777 data/prometheus
docker compose down
sed -i 's/127\.0\.0\.1/0\.0\.0\.0/g' /opt/openrelik/docker-compose.yml
sed -i "s/localhost/$IP_ADDRESS/g" /opt/openrelik/config.env
sed -i "s/localhost/$IP_ADDRESS/g" /opt/openrelik/config/settings.toml

# --- Ensure legacy storage_path is present for older server images ---
CONFIG_TOML="/opt/openrelik/config/settings.toml"
LEGACY_STORAGE_PATH='storage_path = "/usr/share/openrelik/data/artifacts"'

# Ensure [server] section exists
grep -q '^\[server\]' "$CONFIG_TOML" || echo -e '\n[server]' >> "$CONFIG_TOML"

# If storage_path isn't defined anywhere, add it under [server]
grep -q '^[[:space:]]*storage_path[[:space:]]*=' "$CONFIG_TOML" || \
  sed -i "/^\[server\]/a $LEGACY_STORAGE_PATH" "$CONFIG_TOML"
# -------------------------------------------------------------------

docker compose up -d

# --- Upgrade Plaso inside openrelik-worker-plaso to match Timesketch (PPA gift/stable) ---
echo "Upgrading Plaso in openrelik-worker-plaso to match Timesketch..."

# Wait a moment for containers to be ready (optional but helps avoid exec race)
sleep 3

docker compose exec -T openrelik-worker-plaso bash -lc '
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update

# Ensure add-apt-repository is available
if ! command -v add-apt-repository >/dev/null 2>&1; then
  apt-get install -y software-properties-common
fi

# Add gift/stable PPA if not already present
if ! grep -Rqs "ppa.launchpadcontent.net/gift/stable" /etc/apt/sources.list /etc/apt/sources.list.d/*; then
  add-apt-repository -y ppa:gift/stable
fi

apt-get update

# Install/upgrade Plaso packages from the PPA
apt-get install -y plaso-data plaso-tools python3-plaso

echo "Plaso versions now:"
dpkg --list | grep plaso || true
log2timeline.py --version || true
psort.py --version || true
'

# Restart the worker so it picks up the new plaso tooling
docker compose restart openrelik-worker-plaso

# --- Reconcile the OpenRelik admin user ---
# Upstream's "[8/8] Creating admin user" step runs `admin.py create-user` with
# stdout sent to /dev/null and never checks the exit code, then prints "Done"
# and the password unconditionally. So both failure modes are invisible:
#   a) the user already exists (a re-run, or a previous partial install) —
#      create-user exits 1 and the OLD password stays in effect, while the
#      installer cheerfully prints the NEW one, which does not work;
#   b) the create failed outright and no user exists at all.
# Either way the operator is left with a printed password that can't log in.
# Reconcile it explicitly: create the user, and if it already exists, force the
# password to the value the operator actually asked for.
if [ -n "$OPENRELIK_ADMIN_PASSWORD" ]; then
  echo "Verifying OpenRelik admin user..."
  if docker compose exec -T openrelik-server python admin.py create-user admin \
       --password "$OPENRELIK_ADMIN_PASSWORD" --admin >/dev/null 2>&1; then
    echo "  Admin user created."
  elif docker compose exec -T openrelik-server python admin.py change-password admin \
       --password "$OPENRELIK_ADMIN_PASSWORD" >/dev/null 2>&1; then
    echo "  Admin user already existed; password reset to \$OPENRELIK_ADMIN_PASSWORD."
  else
    echo "  ERROR: could not create or update the OpenRelik admin user." >&2
    echo "  Fix it manually with:" >&2
    echo "    cd /opt/openrelik && docker compose exec -T openrelik-server \\" >&2
    echo "      python admin.py create-user admin --password 'YOUR_PASSWORD' --admin" >&2
    exit 1
  fi
else
  echo "WARNING: OPENRELIK_ADMIN_PASSWORD is not set — leaving the admin" >&2
  echo "         credentials as printed by the OpenRelik installer above." >&2
fi
# ------------------------------------------

# Configure OpenRelik API key
# Target the OPENRELIK_API_KEY line directly instead of the YOUR_API_KEY
# placeholder — placeholder-based sed silently no-ops on a re-run, leaving the
# stale key from a previous deploy (whose admin user has since been wiped).
OPENRELIK_API_KEY="$(docker compose exec openrelik-server python admin.py create-api-key admin --key-name "demo")"
OPENRELIK_API_KEY=$(echo "$OPENRELIK_API_KEY" | tr -d '[:space:]')
sed -i -E "s#(OPENRELIK_API_KEY:[[:space:]]*).*#\\1\"$OPENRELIK_API_KEY\"#" /opt/openrelik-pipeline/docker-compose.yml

# Deploy OpenRelik Timesketch worker
# Upstream openrelik-deploy stopped shipping this worker AND stopped declaring
# OPENRELIK_WORKER_TIMESKETCH_VERSION in config.env, so the compose image tag
# resolves to an empty string and `docker compose up` errors with
# "invalid reference format". Pin it ourselves.
echo "Deploying OpenRelik Timesketch worker..."
grep -q '^OPENRELIK_WORKER_TIMESKETCH_VERSION=' config.env || \
  echo 'OPENRELIK_WORKER_TIMESKETCH_VERSION=latest' >> config.env

line=$(grep -n "^volumes:" docker-compose.yml | head -n1 | cut -d: -f1)
insert_line=$((line - 1))

sed -i "${insert_line}i\\
  \\
  openrelik-worker-timesketch:\\
      container_name: openrelik-worker-timesketch\\
      image: ghcr.io/openrelik/openrelik-worker-timesketch:\${OPENRELIK_WORKER_TIMESKETCH_VERSION}\\
      restart: always\\
      environment:\\
        - REDIS_URL=redis://openrelik-redis:6379\\
        - TIMESKETCH_SERVER_URL=http://timesketch-web:5000\\
        - TIMESKETCH_SERVER_PUBLIC_URL=http://$IP_ADDRESS\\
        - TIMESKETCH_USERNAME=admin\\
        - TIMESKETCH_PASSWORD=$TIMESKETCH_PASSWORD\\
      volumes:\\
        - ./data:/usr/share/openrelik/data\\
      command: \"celery --app=src.app worker --task-events --concurrency=1 --loglevel=INFO -Q openrelik-worker-timesketch\"
" docker-compose.yml

# Deploy OpenRelik Hayabusa worker
# Upstream openrelik-deploy no longer ships hayabusa, and the worker repo moved
# from openrelik/ to openrelik-contrib/. Inject it the same way as timesketch.
echo "Deploying OpenRelik Hayabusa worker..."
grep -q '^OPENRELIK_WORKER_HAYABUSA_VERSION=' config.env || \
  echo 'OPENRELIK_WORKER_HAYABUSA_VERSION=latest' >> config.env

line=$(grep -n "^volumes:" docker-compose.yml | head -n1 | cut -d: -f1)
insert_line=$((line - 1))

sed -i "${insert_line}i\\
  \\
  openrelik-worker-hayabusa:\\
      container_name: openrelik-worker-hayabusa\\
      image: ghcr.io/openrelik-contrib/openrelik-worker-hayabusa:\${OPENRELIK_WORKER_HAYABUSA_VERSION}\\
      restart: always\\
      environment:\\
        - REDIS_URL=redis://openrelik-redis:6379\\
      volumes:\\
        - ./data:/usr/share/openrelik/data\\
      command: \"celery --app=src.app worker --task-events --concurrency=4 --loglevel=INFO -Q openrelik-worker-hayabusa\"
" docker-compose.yml

# Idempotent — `docker network connect` errors if endpoint already exists.
docker network inspect openrelik_default --format '{{range .Containers}}{{.Name}} {{end}}' | grep -qw timesketch-web || \
  docker network connect openrelik_default timesketch-web
docker compose up -d

# Deploy OpenRelik pipeline 
echo "Deploying the OpenRelik pipeline..."
cd /opt/openrelik-pipeline
# Same idempotency concern as the API key sed above.
sed -i -E "s#(TIMESKETCH_PASSWORD:[[:space:]]*).*#\\1\"$TIMESKETCH_PASSWORD\"#" ./docker-compose.yml
docker compose build
docker compose up -d
# openrelik-pipeline auto-joins openrelik_default via its compose `networks:` —
# only call connect if it isn't already attached.
docker network inspect openrelik_default --format '{{range .Containers}}{{.Name}} {{end}}' | grep -qw openrelik-pipeline || \
  docker network connect openrelik_default openrelik-pipeline

# Deploy Velociraptor 
echo "Deploying Velociraptor..."
mkdir /opt/velociraptor
cd /opt/velociraptor 
echo """services:
  velociraptor:
    container_name: velociraptor
    restart: always
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ./:/opt:rw
    environment:
      - VELOCIRAPTOR_PASSWORD=${VELOCIRAPTOR_PASSWORD}
      - IP_ADDRESS=${IP_ADDRESS}
    ports:
      - "8000:8000"
      - "8001:8001"
      - "8889:8889" """ | sudo tee -a ./docker-compose.yml > /dev/null

echo "FROM ubuntu:22.04
COPY ./entrypoint .
RUN chmod +x entrypoint && \
    apt update && \
    apt install -y curl wget jq 
WORKDIR /
CMD [\"/entrypoint\"]" | sudo tee ./Dockerfile > /dev/null

cat << EOF | sudo tee entrypoint > /dev/null
#!/bin/bash
set -e

cd /opt

# Use -s (non-empty) instead of -f (exists): if a previous boot left a 0-byte
# server.config.yaml (because the binary download failed), redo the bootstrap.
if [ ! -s server.config.yaml ]; then
  mkdir -p /opt/vr_data

  # Fetch the latest Linux binary URL — first-boot DNS/network can be flaky,
  # so retry until we get a non-empty URL.
  LINUX_BIN=""
  for _ in 1 2 3 4 5; do
    LINUX_BIN=\$(curl -fsSL https://api.github.com/repos/velocidex/velociraptor/releases/latest \
      | jq -r '[.assets[] | select(.name | test("linux-amd64$"))][0].browser_download_url')
    if [ -n "\$LINUX_BIN" ] && [ "\$LINUX_BIN" != "null" ]; then break; fi
    sleep 5
  done
  if [ -z "\$LINUX_BIN" ] || [ "\$LINUX_BIN" = "null" ]; then
    echo "Failed to resolve velociraptor download URL" >&2
    exit 1
  fi

  wget -O /opt/velociraptor "\$LINUX_BIN"
  if [ ! -s /opt/velociraptor ]; then
    rm -f /opt/velociraptor
    echo "velociraptor binary download produced an empty file" >&2
    exit 1
  fi
  chmod +x /opt/velociraptor

  # Generate config with your environment variable expansions.
  ./velociraptor config generate > server.config.yaml --merge '{
    "Frontend": {"hostname": "$IP_ADDRESS"},
    "API": {"bind_address": "0.0.0.0"},
    "GUI": {"public_url": "https://$IP_ADDRESS:8889/app/index.html", "bind_address": "0.0.0.0"},
    "Monitoring": {"bind_address": "0.0.0.0"},
    "Logging": {"output_directory": "/opt/vr_data/logs", "separate_logs_per_component": true},
    "Client": {"server_urls": ["https://$IP_ADDRESS:8000/"], "use_self_signed_ssl": true},
    "Datastore": {"location": "/opt/vr_data", "filestore_directory": "/opt/vr_data"}
  }'

  # Add admin user with the password from the env variable.
  ./velociraptor --config /opt/server.config.yaml user add admin "$VELOCIRAPTOR_PASSWORD" --role administrator
fi

# Finally, run the server.
exec /opt/velociraptor --config /opt/server.config.yaml frontend -v
EOF

docker compose build
docker compose up -d
docker network inspect openrelik_default --format '{{range .Containers}}{{.Name}} {{end}}' | grep -qw velociraptor || \
  docker network connect openrelik_default velociraptor

# --- Pre-load Velociraptor artifact definitions ---------------------------
# Upstream velociraptor no longer bundles the Windows.Triage.Targets artifact,
# and our four Server.Utils.* artifacts (used by the openrelik-pipeline
# endpoints) used to require a manual import via the GUI. Drop both into the
# datastore directly so the install is fully unattended. Same source as the
# build_collector.sh approach in Digital-Defense-Institute/triage.zip.
echo "Importing Velociraptor artifact definitions..."
command -v unzip >/dev/null 2>&1 || apt-get install -y unzip

ARTIFACT_ROOT=/opt/velociraptor/vr_data/artifact_definitions

# /opt/velociraptor/vr_data is created by the entrypoint on first boot.
for _ in $(seq 1 60); do
  [ -d /opt/velociraptor/vr_data ] && break
  sleep 2
done

mkdir -p "$ARTIFACT_ROOT/Server/Utils" "$ARTIFACT_ROOT/Windows/Triage"
cp /opt/openrelik-pipeline/velociraptor/Server.Utils.*.yaml \
   "$ARTIFACT_ROOT/Server/Utils/"

TMP_TRIAGE=$(mktemp -d)
curl -fsSL https://triage.velocidex.com/artifacts/Windows.Triage.Targets.zip \
  -o "$TMP_TRIAGE/triage.zip"
unzip -oq "$TMP_TRIAGE/triage.zip" -d "$ARTIFACT_ROOT/Windows/Triage"
rm -rf "$TMP_TRIAGE"

# Restart so velociraptor rescans artifact_definitions.
docker compose restart velociraptor
