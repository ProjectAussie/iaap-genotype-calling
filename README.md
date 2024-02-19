# Illumina Intensity File --> Call converter
Exploratory project for converting idats >> gtc files.  Once converted, these files can convert calls into norm R/theta values for manually generating cluster plots.

Illumina Array Analysis Platform (IAAP) cli docs:  [https://support.illumina.com/downloads/iaap-genotyping-cli.html](https://support.illumina.com/downloads/iaap-genotyping-cli.html)
# iaap-genotype-calling

`docker build --secret id=awscredentials,src=$(echo ~)/.aws/credentials . -t 074763112859.dkr.ecr.us-east-1.amazonaws.com/embark/iaap:latest`

`docker run -it -v $HOME/.aws:/root/.aws:ro 074763112859.dkr.ecr.us-east-1.amazonaws.com/embark/iaap:latest`
