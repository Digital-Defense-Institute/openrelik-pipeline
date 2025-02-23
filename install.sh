#!/bin/bash

# Set working directory to /opt
cd /opt || exit 1

# Deploy Timesketch
echo "Deploying Timesketch..."
curl -s -O https://raw.githubusercontent.com/google/timesketch/master/contrib/deploy_timesketch.sh
chmod 755 deploy_timesketch.sh
./deploy_timesketch.sh <<EOF
Y
N
EOF

# Change directory to timesketch
cd timesketch || exit 1

# Create Timesketch user
echo -e "${TIMESKETCH_PASSWORD}\n${TIMESKETCH_PASSWORD}" | \
  docker compose exec -T timesketch-web tsctl create-user "$TIMESKETCH_USER"

# Deploy OpenRelik
echo "Deploying OpenRelik..."
cd /opt || exit 1
curl -s -O https://raw.githubusercontent.com/openrelik/openrelik-deploy/main/docker/install.sh

# Run the installation script
bash install.sh

# Set proper permissions for OpenRelik
chmod 777 openrelik/data/prometheus
sleep 10

# Configure OpenRelik
echo "Configuring OpenRelik..."
cd /opt/openrelik || exit 1
docker compose down
sed -i 's/127\.0\.0\.1/0\.0\.0\.0/g' /opt/openrelik/docker-compose.yml
sed -i "s/localhost/$IP_ADDRESS/g" /opt/openrelik/config.env
sed -i "s/localhost/$IP_ADDRESS/g" /opt/openrelik/config/settings.toml
docker compose up -d

# Deploy OpenRelik Timesketch worker
echo "Deploying OpenRelik Timesketch worker..."
echo "

  openrelik-worker-timesketch:
    container_name: openrelik-worker-timesketch
    image: ghcr.io/openrelik/openrelik-worker-timesketch:\${OPENRELIK_WORKER_TIMESKETCH_VERSION}
    restart: always
    environment:
      - REDIS_URL=redis://openrelik-redis:6379
      - TIMESKETCH_SERVER_URL=http://timesketch-web:5000
      - TIMESKETCH_SERVER_PUBLIC_URL=http://$IP_ADDRESS
      - TIMESKETCH_USERNAME=$TIMESKETCH_USER
      - TIMESKETCH_PASSWORD=$TIMESKETCH_PASSWORD
    volumes:
      - ./data:/usr/share/openrelik/data
    command: \"celery --app=src.app worker --task-events --concurrency=1 --loglevel=INFO -Q openrelik-worker-timesketch\"
" | sudo tee -a ./docker-compose.yml > /dev/null

docker network connect openrelik_default timesketch-web
docker compose up -d

# Deploy Velociraptor 
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
    | jq -r '[.assets | sort_by(.created_at) | reverse | .[] | .browser_download_url | select(test("linux-amd64\$"))][0]')

  wget -O /opt/velociraptor "\$LINUX_BIN"
  chmod +x /opt/velociraptor

  # Generate config with your environment variable expansions.
  ./velociraptor config generate > server.config.yaml --merge '{
    "Frontend": {"hostname": "$IP_ADDRESS"},
    "API": {"bind_address": "0.0.0.0"},
    "GUI": {"public_url": "https://$IP_ADDRESS:8889/", "bind_address": "0.0.0.0"},
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
