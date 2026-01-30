# openrelik-pipeline

### Intro
This repository provides an all-in-one DFIR solution by deploying Timesketch, OpenRelik, Velociraptor, and the custom OpenRelik Pipeline tool via Docker Compose. It allows users to send forensic artifacts (e.g., Windows event logs or full triage acquisitions generated with Velociraptor) to an API endpoint, which triggers a workflow to upload the files to OpenRelik and generate a timeline. Depending on the configuration, the workflow can use log2timeline (Plaso) or Hayabusa to produce the timeline and push it directly into Timesketch. This automated approach streamlines artifact ingestion and analysis, turning what used to be multiple separate processes into a more convenient, “push-button” deployment. 

### To do
* <del>Add Velociraptor tags into artifacts so timelines from systems tied to an investigation by tags can all be added to the same sketch for that investigation</del>

### Notes
* There are PRs/issues to make some tweaks in some of the involved repos. 
    * [Fix timeline names for Hayabusa CSV timelines](https://github.com/openrelik/openrelik-worker-hayabusa/issues/4)
    * <del>[Allow users to provide the name of the sketch they want timelines to be part of if it exists instead of just the ID](https://github.com/openrelik/openrelik-worker-timesketch/pull/8)</del>
    * <del>[Ability to set the OpenRelik admin password via an environment variable](https://github.com/openrelik/openrelik-deploy/pull/11)</del>
    * <del>[Ability to create an OpenRelik API key without authing in the web UI](https://github.com/openrelik/openrelik-server/issues/62)
        * This is the main reason manual intervention is required right now and that this cannot be fully scripted. You must log into the OpenRelik web UI in order to generate an API key, and then manually update your `docker-compose.yml` file for the pipeline to work.</del>
    * <del>[Fix for generating a custom Timesketch sketch name vs an auto-generated name](https://github.com/openrelik/openrelik-worker-timesketch/pull/4)</del>

### Known Bugs
* [Timesketch postgres race condition](https://github.com/google/timesketch/issues/3263)

------------------------------

### Step 1 - Install Docker 
Follow the official installation instructions to [install Docker Engine](https://docs.docker.com/engine/install/).

### Step 2 - Clone the project and set environment variables
```bash
sudo -i
git clone https://github.com/Digital-Defense-Institute/openrelik-pipeline.git /opt/openrelik-pipeline
```
Change `IP_ADDRESS` to your public or IPv4 address if deploying on a cloud server, a VM (the IP of the VM), or WSL (the IP of WSL).
```
export TIMESKETCH_PASSWORD="YOUR_DESIRED_TIMESKETCH_PASSWORD"
export VELOCIRAPTOR_PASSWORD="YOUR_DESIRED_VELOCIRAPTOR_PASSWORD"
export OPENRELIK_ADMIN_PASSWORD="YOUR_DESIRED_OPENRELIK_PASSWORD"
export IP_ADDRESS="0.0.0.0" 
```

### Step 3 - Run the install script to deploy Timesketch, OpenRelik, Velociraptor, and the OpenRelik Pipeline
Depending on your connection, this can take 5-10 minutes.
```bash
chmod +x /opt/openrelik-pipeline/install.sh
/opt/openrelik-pipeline/install.sh 
```

> [!NOTE]  
> Your OpenRelik, Velociraptor, Timesketch usernames are `admin`, and the passwords are what you set above.

### Step 4 - Verify deployment
Verify that all containers are up and running.
```bash
docker ps -a
```

Access the web UIs:
* OpenRelik - http://0.0.0.0:8711
* Velociraptor - https://0.0.0.0:8889
* Timesketch - http://0.0.0.0 

Access the pipeline:
* OpenRelik Pipeline - http://0.0.0.0:5000

Again, if deploying elsewhere, or on a VM, or with WSL, use the IP you used for `$IP_ADDRESS`.

### Step 5 - Access 

#### With curl
You can now send files to it for processing and timelining.

We've provided an example with curl so it can be easily translated into anything else.

Generate a timeline with Hayabusa from your Windows event logs and push it into Timesketch:
```bash
curl -X POST -F "file=@/path/to/your/Security.evtx" http://$IP_ADDRESS:5000/api/hayabusa/timesketch
```

Generate a timeline with Plaso and push it into Timesketch:
```bash
curl -X POST -F "file=@/path/to/your/triage.zip" http://$IP_ADDRESS:5000/api/plaso/timesketch
```

#### With Velociraptor
In the repo, we've provided [several Velociraptor artifacts](./velociraptor). 

You can add them in the Velociraptor GUI in one of two ways:  
* In the `View Artifacts` section, click the `Add an Artifact` button and manually copy paste each one and save it  
* Via the Artifact Exchange    
    * Click `Server Artifacts`  
    * Click `New Collection`  
    * Select `Server.Import.ArtifactExchange`  
    * Click `Configure Parameters`  
    * Click on `Server.Import.ArtifactExchange`   
    * For the `ExchangeURL` enter the URL of `velociraptor_artifacts.zip` found [here](https://github.com/Digital-Defense-Institute/openrelik-pipeline/releases/latest)  
    * For the prefix, choose something relevant, like `OpenRelikPipeline.`  
    * Leave `ArchiveGlob` as is  
    * Click `Launch`  
    * You should now see all of them as `Server Monitoring` artifacts in the `Artifacts` page  

These are configured to hit each available endpoint:
* `/api/plaso`
* `/api/plaso/timesketch`
* `/api/hayabusa`
* `/api/hayabusa/timesketch`

You can configure them to run automatically by going to `Server Events` in the Velociraptor GUI and adding them to the server event monitoring table. 

By default, they are configured to run when the `Windows.Triage.Targets` artifact completes on an endpoint. 

It will zip up the collection, and send it through the pipeline into OpenRelik for processing.

  
------------------------------
> [!IMPORTANT]  
> **I strongly recommend deploying OpenRelik and Timesketch with HTTPS**--additional instructions for Timesketch, OpenRelik, and Velociraptor are provided [here](https://github.com/google/timesketch/blob/master/docs/guides/admin/install.md#4-enable-tls-optional), [here](https://github.com/openrelik/openrelik.org/blob/main/content/guides/nginx.md), ahd [here](https://docs.velociraptor.app/docs/deployment/security/#deployment-signed-by-lets-encrypt). For this proof of concept, we're using HTTP. Modify your configs to reflect HTTPS if you deploy for production use. 

