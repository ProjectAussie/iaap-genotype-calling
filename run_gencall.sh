# Download cluster/probe metadata
aws s3 cp s3://genotype-datasets/marker_files/v6_chip_production_probe_lists/Embark_2021_260k_20063270_A1_20211122.egt .
aws s3 cp s3://genotype-datasets/marker_files/v6_chip_production_probe_lists/Embark_2021_260k_20063270_A1.bpm .
aws s3 cp s3://genotype-datasets/marker_files/v6_chip_production_probe_lists/Embark_2021_260k_20063270_A1.csv .
aws s3 sync s3://illumina-embark-sample-level-deliveries/2021-12-14/31001805234805/IDATs/205881370069/ idats

# Copy the ILMN data to the test bucket for safekeeping
aws s3 sync s3://illumina-embark-sample-level-deliveries/2021-12-14/31001805234805 s3://scratch-embark/iaap-test/

# Download an example idat from a new dog
iaap-cli gencall Embark_2021_260k_20063270_A1.bpm Embark_2021_260k_20063270_A1_20211122.egt outputs -f idats -g
aws s3 sync outputs s3://scratch-embark/iaap-test/
# Grab canfam 4 as reference data
aws s3 cp s3://embark-data-drops/canFam4/canFam4.fa .

# Convert outputs to vcf
# Didn't work, only human supported 
# java -jar picard.jar GtcToVcf \
#       INPUT=outputs/205881370069_R11C02.gtc \
#       REFERENCE_SEQUENCE=canFam4.fa \
#       OUTPUT=output.vcf \
#       EXTENDED_ILLUMINA_MANIFEST=Embark_2021_260k_20063270_A1.csv \
#       CLUSTER_FILE=Embark_2021_260k_20063270_A1_20211122.egt \
#       ILLUMINA_BEAD_POOL_MANIFEST_FILE=Embark_2021_260k_20063270_A1.bpm \
#       SAMPLE_ALIAS=test_alias
python gtc_to_vcf.py \
    --gtc-paths /outputs/205881370069_R11C02.gtc \
    --manifest-file /Embark_2021_260k_20063270_A1.csv \
    --genome-fasta-file /canFam4.fa
    
aws s3 sync output.vcf s3://scratch-embark/iaap-test/