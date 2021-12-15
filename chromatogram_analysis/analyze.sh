aws s3 sync s3://embark-data-drops/chromatogram_data/011004/ 011004/
aws s3 cp s3://embark-data-drops/canFam4/canFam4.fa .
aws s3 cp s3://embark-data-drops/canFam4/canFam4.fa.fai .

# Pyruvate Kinase Deficiency	(PKLR Exon 10, Terrier Variant)		7	42269749

export CHROMOSOME=7

# Grab out just the one chromosome
awk '/chr7/,/^\s*$/' canFam4.fa > canFam4_$CHROMOSOME.fa
tail -n +2 canFam4_$CHROMOSOME.fa > canFam4_${CHROMOSOME}_single_line.fa


tracy index canFam4_${CHROMOSOME}_single_line.fa
tracy align -r canFam4_${CHROMOSOME}_single_line.fa 011004/011004-E3-31001809337400-EV1012-20210226.ab1