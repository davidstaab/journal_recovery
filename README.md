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

## The story of this project

Problem:
1. I was using a writer's app called Scrivener to keep a journal. The Scrivener file (which turns out just to be a ZIP of a directory tree) was being sync'd to Dropbox. I lost both the Dropbox copy and the local copy in a catastrophic event.
1. Dropbox had been backed up to a local NAS device with a cronjob tool. Hooray! However, the NAS's disk was also wiped in the same event.
1. I used a file recovery tool on the NAS RAID; it scraped 80,000 RTF files off the disk. All of them were named "File Name Lost (#####).rtf".
1. How to sort these files into copies of the same so I could take the largest of each one as the canonical version?

Solution:
1. First I have to be able to read these files. How to decode RTF? I found a library: [striprtf](https://github.com/joshy/striprtf)
1. Now how do I compare any two files to see if they're similar?
    1. [thefuzz](https://github.com/seatgeek/thefuzz)
    1. But someone wrote a faster one which is still being updated: [rapidfuzz](https://maxbachmann.github.io/RapidFuzz/Installation.html)
1. Now it's working, but it's way, way too slow
    1. Ask ChatGPT to analyze my code for performance issues: It suggests switching to [Jaccard similarity in NLTK](https://www.nltk.org/_modules/nltk/metrics/distance.html#jaccard_distance)
    1. Jaccard doesn't work quite the way I want, so I modify it to a "pseudo-jaccard" that fits my situation. *(See `pseudo_jaccard_similarity()` in sortem.py.)*
1. Much faster! Hooray! But it ties up my laptop while running.
    1. Ask ChatGPT for help again. It say, "Run it in the cloud."
1. So I build it into a Docker container for easy deployment.
    1. I've never done that before, so I ask ChatGPT for help again. It writes me some Dockerfile and compose.yaml snippets, and I figure out what they mean.
1. Find a free cloud provider...(lol)
    1. I get $300 in promo credits on GCE, and they have a container optimized OS. Let's go!
## Ops stuff for my own reference
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
`cd ../files && tar cvzf files.tar.gz * && mv files.tar.gz ~/Desktop`

#### Unzip them on the VM (after they’ve been copied using the remote shell window)
`cd ~ && tar xzf files.tar.gz -C ~/source && rm files.tar.gz`

#### Check on VM progress
*(I could add a HEALTHCHECK directive to the dockerfile to aid this, but I don't really need to and good shell scripting is hard.)*

Logs: `docker ps -aq | xargs -L 1 docker logs -n 20`

Remaining file count: `ls -1q ./source | wc -l`
