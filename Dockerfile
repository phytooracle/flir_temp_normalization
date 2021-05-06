FROM agdrone/drone-base-image:1.2

LABEL maintainer="Cosi Michele <cosi@email.arizona.edu>"

WORKDIR /opt
COPY . /opt

COPY requirements.txt packages.txt /home/extractor/

USER root

ENV IRODS_USER=anonymous

RUN apt-get update && apt-get install -y \
    apt-transport-https \
    gcc \
    gnupg \
    wget 

RUN wget https://files.renci.org/pub/irods/releases/4.1.10/ubuntu14/irods-icommands-4.1.10-ubuntu14-x86_64.deb \
    && apt-get install -y ./irods-icommands-4.1.10-ubuntu14-x86_64.deb

RUN [ -s /home/extractor/packages.txt ] && \
    (echo 'Installing packages' && \
        apt-get update && \
        cat /home/extractor/packages.txt | xargs apt-get install -y --no-install-recommends && \
        mkdir -p /root/.irods && \
        echo "{ \"irods_zone_name\": \"iplant\", \"irods_host\": \"data.cyverse.org\", \"irods_port\": 1247, \"irods_user_name\": \"$IRODS_USER\" }" > /root/.irods/irods_environment.json && \
        rm /home/extractor/packages.txt && \
        apt-get autoremove -y && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/*) || \
    (echo 'No packages to install' && \
        rm /home/extractor/packages.txt)

RUN [ -s /home/extractor/requirements.txt ] && \
    (echo "Install python modules" && \
    python3 -m pip install -U --no-cache-dir pip && \
    python3 -m pip install --no-cache-dir setuptools && \
    python3 -m pip install --no-cache-dir -r /home/extractor/requirements.txt && \
    rm /home/extractor/requirements.txt) || \
    (echo "No python modules to install" && \
    rm /home/extractor/requirements.txt)

#USER extractor
USER root

COPY *.py /home/extractor/

ENTRYPOINT [ "/usr/bin/python3", "/opt/temp_normalization.py" ]
