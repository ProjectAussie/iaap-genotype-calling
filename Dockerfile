FROM ubuntu:20.04

# Install aws cli
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive && \
    apt-get install -y --quiet --assume-yes --no-install-recommends  \
        python3 \
        python3-pip \
        python3-setuptools \
        groff \
        less \
        awscli \
        icu-devtools \
        wget \
        python2 gcc python2-dev \
        libbz2-dev make zlib1g-dev libncurses5-dev libncursesw5-dev liblzma-dev \
        git \
    && pip3 install --upgrade pip \
    && apt-get clean

# Install htslib
ARG htsversion=1.3
RUN curl -L https://github.com/samtools/htslib/releases/download/${htsversion}/htslib-${htsversion}.tar.bz2 | tar xj && \
    (cd htslib-${htsversion} && ./configure --enable-plugins --with-plugin-path='$(libexecdir)/htslib:/usr/libexec/htslib' && make install) && \
    ldconfig && \
    curl -L https://github.com/samtools/samtools/releases/download/${htsversion}/samtools-${htsversion}.tar.bz2 | tar xj && \
    (cd samtools-${htsversion} && ./configure --with-htslib=system && make install) && \
    curl -L https://github.com/samtools/bcftools/releases/download/${htsversion}/bcftools-${htsversion}.tar.bz2 | tar xj && \
    (cd bcftools-${htsversion} && ./configure --enable-libgsl --enable-perl-filters --with-htslib=system && make install) && \
    git clone --depth 1 git://github.com/samtools/htslib-plugins && \
    (cd htslib-plugins && make PLUGINS='hfile_cip.so hfile_mmap.so' install)

# Install ILMN gtc to vcf (note tha hstlib 1.3 is required for pysam 0.9.0, which is the pinned version for ILMN gtc to vcf)
# However, calvin got things to install with hts lib 1.9
RUN python get-pip.py && \
    pip2 install numpy==1.11.2 pyvcf==0.6.8 pysam==0.9.0 && \
    git clone https://github.com/Illumina/GTCtoVCF.git
    

# Install ILMN IAAP CLI for idat to gtc conversion
RUN --mount=type=secret,id=awscredentials,target=/root/.aws/credentials \
    export AWS_PROFILE=prod && \
    export AWS_CONFIG_FILE=/root/.aws/credentials && \
    cd $HOME && \
    aws s3 cp s3://scratch-embark/iaap/iaap-cli-linux-x64-1.1.0-sha.80d7e5b3d9c1fdfc2e99b472a90652fd3848bbc7.tar.gz . && \
    tar -xf $HOME/iaap-cli-linux-x64-1.1.0-sha.80d7e5b3d9c1fdfc2e99b472a90652fd3848bbc7.tar.gz && \
    chmod +x $HOME/iaap-cli-linux-x64-1.1.0-sha.80d7e5b3d9c1fdfc2e99b472a90652fd3848bbc7/iaap-cli/iaap-cli && \
    rm $HOME/iaap-cli-linux-x64-1.1.0-sha.80d7e5b3d9c1fdfc2e99b472a90652fd3848bbc7.tar.gz

ENV PATH="/root/iaap-cli-linux-x64-1.1.0-sha.80d7e5b3d9c1fdfc2e99b472a90652fd3848bbc7/iaap-cli:$PATH"

# Install picard for gtc to vcf/bcf conversion
# Note: This doesn't work, only supports human
RUN apt-get update && \
    apt-get install -y openjdk-8-jdk && \
    apt-get install -y ant && \
    wget https://github.com/broadinstitute/picard/releases/download/2.26.7/picard.jar && \
    apt-get clean;

ENV AWS_CONFIG_FILE=/root/.aws/config
ENV AWS_PROFILE=prod

# Build this repo into container
ADD ./* /root/
