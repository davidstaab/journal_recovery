FROM python:3.10-slim

# app directory within the container
WORKDIR /home/app

# pull the project from github
RUN apt-get update && apt-get install -y git
RUN git clone --verbose --branch gcloud --recurse-submodules https://github.com/davidstaab/journal_recovery.git .

# install required python modules
RUN python3 -m pip install --upgrade pip
RUN pip3 install --no-cache-dir -r ./requirements.txt

CMD [ "python", "./sortem/sortem.py" ]
