FROM python:3.10-slim

# app directory within the container
WORKDIR /home/app

# pull the project from github (good for building on a non-dev workstation, I guess?)
# RUN apt-get update && apt-get install -y git
# RUN git clone --verbose --branch gcloud --recurse-submodules https://github.com/davidstaab/journal_recovery.git .

# (instead of above) copy project files to container
COPY . .

# install required python modules
RUN python3 -m pip install --upgrade pip
RUN pip3 install --no-cache-dir -r ./requirements.txt

CMD [ "python", "./sortem/sortem.py" ]
