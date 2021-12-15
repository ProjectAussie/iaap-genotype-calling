FROM geargenomics/tracy
WORKDIR /

FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --quiet --assume-yes --no-install-recommends  \
        python3 \
        python3-pip \
        python3-setuptools \
        groff \
        less \
        awscli \
        icu-devtools \
        wget \
        git curl \
    && apt-get clean

ADD ./ /

COPY --from=0 /opt/tracy/ /tracy
ENV PATH=$PATH:/tracy/bin/
ENV AWS_PROFILE=prod
ENV AWS_CONFIG_FILE=/root/.aws/config
ENV DEBIAN_FRONTEND=newt