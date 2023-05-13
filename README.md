# journal_recovery
A python script to recover my personal journal from 80k .rtf file fragments scraped off a backup drive

## How to run it
`git clone --recurse-submodules` the repo, then: `docker-compose build --no-cache --progress=plain`

and then: `docker-compose up`

### Environment config

It's going to look for files to sort (and where to put them) in the path specified by two bits of code:
* In compose.yaml, the host mount points under `volumes:`
* In sortem.py, the defines `SOURCE_DIR` and `SORTING_DIR` after the include statements

If you change a path, change it in both places.

## More ops stuff for my own reference
### Run the container locally
`cd app && docker compose build --no-cache`

`docker compose up`

### Run on GCE VM
Note: vm target platform: `linux/amd64/v4`

#### 1. Build and push the container image (dev machine shell)
```bash
docker build --no-cache --platform linux/amd64 -t gcr.io/reliable-return-384618/sortem-image . \
&& docker push gcr.io/reliable-return-384618/sortem-image
```

#### 2. Bounce the VM (local shell)
`gcloud compute instances stop sortem-worker`

`gcloud compute instances start sortem-worker`

### Utilities
#### SSH via terminal. Better just to use Google's shell window in Gcloud web.
`gcloud compute ssh --project=reliable-return-384618 --zone=us-west4-b sortem-worker`

#### Make a huge batch of files
`cd ../files && tar czf files.tar.gz * && mv files.tar.gz ~/Desktop`

#### Unzip them on the VM (after they’ve been copied using the remote shell window)
`cd ~ && tar xvzf files.tar.gz -C ~/source && rm files.tar.gz`

#### Check on VM progress
Logs: `docker ps -q | xargs -L 1 docker logs -n 20`

Remaining file count: `ls -1q ./source | wc -l`

## The story of this project
(TODO)

Problem:
1. Backing up a Scrivener file with Dropbox, lost the DB copy and the local copy
1. DB had been backed up to a local NAS box with a regular cloning tool
1. File recovery on the NAS RAID scraped 80k RTF files
1. How to sort the files into copies of the same?

Solution:
1. Decode RTF
1. Find a comparison module
    1. thefuzz
    1. rapidfuzz
1. Way, way too slow
    1. Ask ChatGPT for help: jaccard similarity
    1. pseudo-jaccard to meet my situation
1. Faster! Hooray! But it ties up my laptop
    1. Ask ChatGPT again: run it in the cloud
1. Build it into a Docker container
    1. Ask ChatGPT for help again
1. (Next step) Find a free cloud provider...
