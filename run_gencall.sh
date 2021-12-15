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
aws s3 cp s3://embark-data-drops/canFam4/canFam4.fa.fai .
# Rename chrX to X, which is what ILMN expects based on hg19
cat canFam4.fa | sed -r 's/chr([0-9XM]*)/\1/g' > canFam4.fa
cat canFam4.fa.fai | sed -r 's/chr([0-9XM]*)/\1/g' > canFam4.fa.fai

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

# Insert ref strand data artificially into csv
# To do this, add a + into every row in the 19th column
#however, the first row is a header, so use sed to replace the plus in the first row with the column name
# TODO: Bug MarkH to get a manifest that has this column
awk -F"," 'BEGIN { OFS = "," } {$19="+"; print}' /Embark_2021_260k_20063270_A1.csv > /Embark_2021_260k_20063270_A1_tweaked.csv
sed 's/TopGenomicSeq,+/TopGenomicSeq,refstrand/' /Embark_2021_260k_20063270_A1_tweaked.csv > /Embark_2021_260k_20063270_A1_tweaked2.csv

# Also note that gtc_to_vcf.py expects contigs to be named like "8" instead of "chr8"
python2 GTCtoVCF/gtc_to_vcf.py \
    --gtc-paths /outputs/205881370069_R11C02.gtc \
    --manifest-file /Embark_2021_260k_20063270_A1_tweaked2.csv \
    --genome-fasta-file /canFam4.fa \
    --skip-indels # Skip indels required when using bpm manifest. Need extended csv manifest.
    
aws s3 sync output.vcf s3://scratch-embark/iaap-test/