#!/bin/bash

# Set working directory to /opt
cd /opt 

# Deploy Timesketch
echo "Deploying Timesketch..."
curl -s -O https://raw.githubusercontent.com/google/timesketch/master/contrib/deploy_timesketch.sh
chmod 755 deploy_timesketch.sh
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
bash install.sh

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

# Configure OpenRelik API key 
OPENRELIK_API_KEY="$(docker compose exec openrelik-server python admin.py create-api-key admin --key-name "demo")"
OPENRELIK_API_KEY=$(echo "$OPENRELIK_API_KEY" | tr -d '[:space:]')
sed -i "s#YOUR_API_KEY#$OPENRELIK_API_KEY#g" /opt/openrelik-pipeline/docker-compose.yml

# Deploy OpenRelik Timesketch worker
echo "Deploying OpenRelik Timesketch worker..."
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

docker network connect openrelik_default timesketch-web
docker compose up -d

# Deploy OpenRelik pipeline 
echo "Deploying the OpenRelik pipeline..."
cd /opt/openrelik-pipeline 
sed -i "s/YOUR_TIMESKETCH_PASSWORD/$TIMESKETCH_PASSWORD/g" ./docker-compose.yml
docker compose build 
docker compose up -d 
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

cd /opt

if [ ! -f server.config.yaml ]; then
  mkdir -p /opt/vr_data

  # Fetch the latest Linux binary.
  LINUX_BIN=\$(curl -s https://api.github.com/repos/velocidex/velociraptor/releases/latest \
    | jq -r '[.assets[] | select(.name | test("linux-amd64$"))][0].browser_download_url')
    
  wget -O /opt/velociraptor "\$LINUX_BIN"
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
docker network connect openrelik_default velociraptor
