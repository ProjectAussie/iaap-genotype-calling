"""
This script generates genotype call (.gtc) files
from raw intensity data (.idats) and extracts
NormR and NormTheta values at all array markers
for a list of dogs (swab codes), or all dogs in specified deliveries.

The operations the script performs require a lot of disk space,
and it has not been tested on a lower RAM machine,
so it is recommended that it be run on an ec2 instance instead of locally.

TODO: add functionality to restrict data to a subset of markers rather than entire array

Example usage:

`python generate_normalized_intensity_data_for_swabs_or_deliveries.py
    --delivery-names embark_2021-12-26_0609
    --cluster-file-s3-path s3://illumina-embark-data/Cluster_Files_Updated_Monthly/Embark_2021_260k_20063270_A1_20211122.egt
    --beadpool-manifest-s3-path s3://illumina-embark-data/beadpool-manifests/Embark_2021_260k_20063270_A1.bpm
    --output-dir /home/ubuntu/idat_to_gtc_test
`

"""

import argparse
import functools
import os
import shutil
from typing import List
from multiprocessing import Pool, cpu_count
from pathlib import Path
import pandas as pd
import numpy as np
from IlluminaBeadArrayFiles import GenotypeCalls, BeadPoolManifest
from pybark import db, s3, shell

POOL_SIZE = cpu_count() * 2
env_folder = s3.env_folder("prod")
s3_bucket = "illumina-embark-data"


def _get_delivery_names_for_swab_codes(swab_codes: List[str]) -> pd.DataFrame:
    results_df = pd.DataFrame(
        db.run_query(
            ENVIRONMENT=db.get_environment(),
            sql="SELECT illumina_delivery_name, swab_code FROM genotypes WHERE swab_code IN %(swab_codes)s",
            substitutions={"swab_codes": tuple(swab_codes)},
        ),
    )
    return results_df


def _get_swab_codes_for_delivery_names(delivery_names: List[str]) -> pd.DataFrame:
    results_df = pd.DataFrame(
        db.run_query(
            ENVIRONMENT=db.get_environment(),
            sql="SELECT illumina_delivery_name, swab_code FROM genotypes WHERE illumina_delivery_name IN %(delivery_names)s",
            substitutions={"delivery_names": tuple(delivery_names)},
        ),
    )
    return results_df


def _download_idats(output_dir: Path, record: dict) -> None:
    swab_code = record["swab_code"]
    sentrix_id = record["sentrix_id"]
    sentrix_position = record["sentrix_position"]
    delivery_name = record["illumina_delivery_name"]
    for color in "Grn", "Red":
        idat_s3_path = s3.construct_s3_url(
            bucket=s3_bucket,
            key=f"{env_folder}unzipped/{delivery_name}/{swab_code}/IDATs/{sentrix_id}/{sentrix_id}_{sentrix_position}_{color}.idat",
        )
        s3.download_file(
            idat_s3_path, f"{output_dir}/idats/{sentrix_id}_{sentrix_position}_{color}.idat"
        )


def _make_gtcs_from_idats_for_dir(delivery_data_dir: Path, beadpool_manifest_path: Path, cluster_file_path: Path) -> None:
    # Generate .gtc file from .idat file pair using Illumina GenCall via IAAP CLI
    print(" ".join(["iaap-cli", "gencall", beadpool_manifest_path, cluster_file_path, f"{delivery_data_dir}/gtcs", "--idat-folder", f"{delivery_data_dir}/idats", "--num-threads", f"{cpu_count() - 1}", "--output-gtc"]))
    shell.call_shell_cmd(
        [
            "iaap-cli", "gencall", beadpool_manifest_path, cluster_file_path, f"{delivery_data_dir}/gtcs", 
            "--idat-folder", f"{delivery_data_dir}/idats",
            "--num-threads", f"{cpu_count() - 1}",
            "--output-gtc"
        ],
    )


def _get_NormR_NormTheta_values_from_gtc(gtc_file, bpm_normalization_lookups, bpm_names) -> pd.DataFrame:
    def convert_rect_coord_to_polar(coord):
        x, y = coord[0], coord[1]
        if x == 0 and y == 0:
            return (np.nan, np.nan)
        return (x + y, np.arctan2(y, x) * 2.0 / np.pi)

    gtc = GenotypeCalls(gtc_file)
    normalized_intensities = gtc.get_normalized_intensities(bpm_normalization_lookups)
    polar_normalized_intensities = list(map(convert_rect_coord_to_polar, normalized_intensities))
    marker_normalized_intensity_vals_dict = dict(zip(bpm_names, polar_normalized_intensities))
    marker_normalized_intensity_vals_df = pd.DataFrame.from_dict(marker_normalized_intensity_vals_dict, orient="index", columns=["NormR", "NormTheta"])
    marker_normalized_intensity_vals_df.index.name = "Name"
    return marker_normalized_intensity_vals_df


def _make_normalized_intensity_file_from_idats_for_record(delivery_data_dir, bpm_normalization_lookups, bpm_names, record):
    sentrix_id = record["sentrix_id"]
    sentrix_position = record["sentrix_position"]
    genotype_id = f"{record['sample_id']}_{record['swab_code']}"
    gtc_file = os.path.join(delivery_data_dir, f"gtcs/{sentrix_id}_{sentrix_position}.gtc")
    # Generate .tsv file containing NormR, NormTheta
    marker_normalized_intensity_vals_df = _get_NormR_NormTheta_values_from_gtc(
        gtc_file, bpm_normalization_lookups, bpm_names,
    )
    marker_normalized_intensity_vals_df.reset_index().to_csv(f"{delivery_data_dir}/{genotype_id}_normalized_intensity.tsv", index=False, sep="\t")


def main(
    delivery_names,
    swab_code_file,
    output_dir,
    cluster_file_s3_path,
    beadpool_manifest_s3_path,
):
    deliveries_to_run_df = pd.DataFrame()

    # Get delivery info for all swab codes in input list
    if swab_code_file:
        swab_codes = shell.lines_from_file(swab_code_file)
        deliveries_with_target_swabs_df = _get_delivery_names_for_swab_codes(swab_codes)
        deliveries_to_run_df = deliveries_to_run_df.append(deliveries_with_target_swabs_df, ignore_index=True)

    else:
        delivery_list = delivery_names.split(",")
        target_delivery_swabs_df = _get_swab_codes_for_delivery_names(delivery_list)
        deliveries_to_run_df = deliveries_to_run_df.append(target_delivery_swabs_df, ignore_index=True)

    print(deliveries_to_run_df.value_counts(subset=["illumina_delivery_name"]))

    for _delivery_name, _delivery_df in deliveries_to_run_df.groupby("illumina_delivery_name"):
        output_dir_path = Path(output_dir)
        delivery_data_dir = os.path.join(output_dir_path, _delivery_name)
        shell.mkdir_p(delivery_data_dir)
        idats_dir_path = os.path.join(delivery_data_dir, "idats")
        shell.mkdir_p(idats_dir_path)
        gtc_dir_path = os.path.join(delivery_data_dir, "gtcs")
        shell.mkdir_p(gtc_dir_path)

        # Fetch the sample report .csv from s3 to get sentrix info for swabs
        sample_report_key = (f"{env_folder}unzipped/{_delivery_name}/{_delivery_name}-SampleReport.csv")
        sample_report_df = s3.fetch_csv(bucket=s3_bucket, key=sample_report_key)
        sample_report_df["illumina_delivery_name"] = _delivery_name
        sample_report_df["swab_code"] = sample_report_df["embark_id"].astype(str)
        filtered_sample_report_df = sample_report_df.merge(_delivery_df, on=["illumina_delivery_name", "swab_code"], how='inner')
        filtered_sample_report_records = filtered_sample_report_df.to_dict("records")

        print("Downloading .idats for delivery " + _delivery_name)
        _download_func = functools.partial(_download_idats, delivery_data_dir)
        with Pool(POOL_SIZE) as pool:
            pool.map(_download_func, filtered_sample_report_records)
        print("Finished downloading .idats")

        print("Generating .gtc files from .idats for delivery " + _delivery_name)
        cluster_file_path = os.path.join(delivery_data_dir, cluster_file_s3_path.split("/")[-1])
        s3.download_file(cluster_file_s3_path, cluster_file_path)
        beadpool_manifest_path = os.path.join(delivery_data_dir, beadpool_manifest_s3_path.split("/")[-1])
        s3.download_file(beadpool_manifest_s3_path, beadpool_manifest_path)
        _make_gtcs_from_idats_for_dir(delivery_data_dir, beadpool_manifest_path, cluster_file_path)
        print("Finished generating .gtcs")

        print("Generating NormR, NormTheta files from .gtcs for delivery " + _delivery_name)
        manifest = BeadPoolManifest(beadpool_manifest_path)
        bpm_normalization_lookups = manifest.normalization_lookups
        bpm_names = manifest.names
        _make_normalized_intensity_file_func = functools.partial(_make_normalized_intensity_file_from_idats_for_record, delivery_data_dir, bpm_normalization_lookups, bpm_names)
        with Pool(POOL_SIZE) as pool:
            pool.map(_make_normalized_intensity_file_func, filtered_sample_report_records)
        print("Finished generating NormR, NormTheta .tsvs")

        # Delete .idats and .gtcs
        shutil.rmtree(idats_dir_path)
        #shutil.rmtree(gtc_dir_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delivery-names", help="Comma separated string of delivery names (only v2 format currently supported, e.g. 'embark_YYYY-MM-DD_hhmm'",
    )
    parser.add_argument(
        "--swab_code_file", help="Name of single column .txt file with list of swabs to process (no header)", default=None,
    )
    parser.add_argument(
        "--cluster-file-s3-path", help="Path to the cluster file to use on S3.",
    )
    parser.add_argument(
        "--beadpool-manifest-s3-path", help="Path to the BPM file to use on S3.",
    )
    parser.add_argument(
        "--output-dir", help="Path to dir containing outputs.",
    )

    args = parser.parse_args()
    main(
        delivery_names=args.delivery_names,
        cluster_file_s3_path=args.cluster_file_s3_path,
        beadpool_manifest_s3_path=args.beadpool_manifest_s3_path,
        swab_code_file=args.swab_code_file,
        output_dir=args.output_dir,
    )

