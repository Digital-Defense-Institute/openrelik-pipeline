# openrelik-pipeline

### Step 1 - Install Docker 
Follow the official installation instructions to [install Docker Engine](https://docs.docker.com/engine/install/).

### Step 2 - Deploy Timesketch and create an admin user
Additional details can be found in the [Timesketch docs](https://timesketch.org/guides/admin/install/).
```bash
cd /opt
curl -s -O https://raw.githubusercontent.com/google/timesketch/master/contrib/deploy_timesketch.sh
chmod 755 deploy_timesketch.sh
sudo env START_CONTAINER=Y SKIP_CREATE_USER=1 ./deploy_timesketch.sh
docker compose exec timesketch-web tsctl create-user admin 
```

### Step 3 - Deploy OpenRelik
Additional details can be found in the [OpenRelik docs](https://openrelik.org/docs/getting-started/).
```bash
curl -s -O https://raw.githubusercontent.com/openrelik/openrelik-deploy/main/docker/install.sh # Modify this if you want
bash install.sh
```
> [!NOTE]  
> This will generate an `admin` user and password. The password will be displayed when the deployment is complete. Be sure to save it.


### Step 4 - Deploy OpenRelik Timesketch worker
Append the following to your `docker-compose.yml`:
```bash
echo "

  openrelik-worker-timesketch:
    container_name: openrelik-worker-timesketch
    image: ghcr.io/openrelik/openrelik-worker-timesketch:\${OPENRELIK_WORKER_TIMESKETCH_VERSION}
    restart: always
    environment:
      - REDIS_URL=redis://openrelik-redis:6379
      - TIMESKETCH_SERVER_URL=http://timesketch-web
      - TIMESKETCH_SERVER_PUBLIC_URL=http://YOUR_TIMESKETCH_URL
      - TIMESKETCH_USERNAME=YOUR_TIMESKETCH_USER
      - TIMESKETCH_PASSWORD=YOUR_TIMESKETCH_PASSWORD
    volumes:
      - ./data:/usr/share/openrelik/data
    command: \"celery --app=src.app worker --task-events --concurrency=1 --loglevel=INFO -Q openrelik-worker-timesketch\"
" | sudo tee -a ./openrelik/docker-compose.yml > /dev/null

```
Then link your Timesketch container to the `openrelik_default` network, and start it:
```bash
docker network connect openrelik_default timesketch-web
docker compose up -d
```

### Step 5 - Verify deployment
```bash
docker ps -a
```
If you see the Prometheus container failing to start, you can try `chmod 777 openrelik/data/prometheus`.  

Log in at `http://localhost:8711`

### Step 6 - Generate an API key
1. Click the user icon in the top right corner
2. Click `API keys`
3. Click `Create API key`
4. Provide a name, click `Create`, copy the key, and save it for Step 7 


### Step 7 - Start the pipeline
Modify your API key in `docker-compose.yml`, then build and run the container.
```bash
docker compose build
docker compose up -d
docker network connect openrelik_default openrelik-pipeline
```

This will start a local server on `http://localhost:5000`.  

You can now send files to it for processing and timelining:

```bash
curl -X POST -F "file=@/path/to/your/file.zip" -F "filename=file.zip" http://localhost:5000/api/plaso/upload

curl -X POST -F "file=@/path/to/your/file.zip" -F "filename=file.zip" http://localhost:5000/api/hayabusa/upload

```

  
------------------------------
> [!IMPORTANT]  
> **I strongly recommend deploying OpenRelik and Timesketch with HTTPS**--additional instructions for Timesketch and OpenRelik are provided [here](https://github.com/google/timesketch/blob/master/docs/guides/admin/install.md#4-enable-tls-optional) and [here](https://github.com/openrelik/openrelik.org/blob/main/content/guides/nginx.md). For this proof of concept, we're using HTTP. Modify your configs to reflect HTTPS if you deploy for production use. 