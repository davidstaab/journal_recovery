# using Google's official Python image for Google Cloud Platform
FROM gcr.io/google-appengine/python

# app directory within the container
WORKDIR /app

# pull the project from github
RUN apt-get update && apt-get install -y git
RUN git clone --verbose --branch docker https://github.com/davidstaab/journal_recovery.git

# install required python modules
RUN python3 -m pip install --upgrade pip
RUN pip3 install --no-cache-dir -r ./requirements.txt

CMD [ "python", "sortem.py" ]
