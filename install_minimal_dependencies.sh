#!/bin/bash

# Install htslib
htsversion=1.3
sudo curl -L https://github.com/samtools/htslib/releases/download/${htsversion}/htslib-${htsversion}.tar.bz2 | tar xj && \
    (cd htslib-${htsversion} && /
    ./configure --enable-plugins --with-plugin-path='$(libexecdir)/htslib:/usr/libexec/htslib' && /
    make install)

# Install Illumina iaap-cli
cd $HOME && \
    aws s3 cp s3://scratch-embark/iaap/iaap-cli-linux-x64-1.1.0-sha.80d7e5b3d9c1fdfc2e99b472a90652fd3848bbc7.tar.gz . && \
    tar -xf $HOME/iaap-cli-linux-x64-1.1.0-sha.80d7e5b3d9c1fdfc2e99b472a90652fd3848bbc7.tar.gz && \
    chmod +x $HOME/iaap-cli-linux-x64-1.1.0-sha.80d7e5b3d9c1fdfc2e99b472a90652fd3848bbc7/iaap-cli/iaap-cli && \
    rm $HOME/iaap-cli-linux-x64-1.1.0-sha.80d7e5b3d9c1fdfc2e99b472a90652fd3848bbc7.tar.gz

PATH="$HOME/iaap-cli-linux-x64-1.1.0-sha.80d7e5b3d9c1fdfc2e99b472a90652fd3848bbc7/iaap-cli:$PATH"

# Install BeadArrayFiles library for Illumina file manipulation
sudo apt-get update -y
sudo apt-get install -y python-distutils-extra
sudo apt-get install -y  python3-distutils
git clone https://github.com/Illumina/BeadArrayFiles.git && \
    cd BeadArrayFiles; python3 setup.py install
