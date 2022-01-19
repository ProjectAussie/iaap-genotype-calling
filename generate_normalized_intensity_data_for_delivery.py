import argparse, functools, os, shutil
from multiprocessing import Pool, cpu_count
import pandas as pd
import numpy as np
from IlluminaBeadArrayFiles import GenotypeCalls, BeadPoolManifest
from pybark import s3, shell

POOL_SIZE = cpu_count() * 2
s3_bucket = "illumina-embark-data"


def _get_NormR_NormTheta_values_from_gtc(gtc_file, bpm_normalization_lookups, bpm_names):

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


def _make_normalized_intensity_file_from_idats_for_record(
    env_folder, delivery_name, delivery_data_dir, beadpool_manifest_path, cluster_file_path, bpm_normalization_lookups, bpm_names, record,
):
    embark_id = record["embark_id"]
    sentrix_id = record["sentrix_id"]
    sentrix_position = record["sentrix_position"]
    genotype_id = f"{record['sample_id']}_{record['embark_id']}"
    #print(f"downloading idat files for {embark_id}")
    for color in "Grn", "Red":
        idat_s3_path = s3.construct_s3_url(
            bucket=s3_bucket,
            key=f"{env_folder}unzipped/{delivery_name}/{embark_id}/IDATs/{sentrix_id}/{sentrix_id}_{sentrix_position}_{color}.idat",
        )
        s3.download_file(
            idat_s3_path, f"{delivery_data_dir}/idats/{sentrix_id}_{sentrix_position}_{color}.idat"
        )

    # Generate .gtc file from .idat file pair using Illumina GenCall via IAAP CLI
    #print(f"generating .gtc file for {embark_id}")
    #print(" ".join(["iaap-cli", "gencall", beadpool_manifest_path, cluster_file_path, f"{delivery_data_dir}/gtcs", "--idat-folder", f"{delivery_data_dir}/idats", "--output-gtc"]))
    shell.call_shell_cmd(
        [
            "iaap-cli", "gencall", beadpool_manifest_path, cluster_file_path, f"{delivery_data_dir}/gtcs", "--idat-folder", f"{delivery_data_dir}/idats", "--output-gtc"
        ],
    )
    gtc_file = os.path.join(delivery_data_dir, f"gtcs/{sentrix_id}_{sentrix_position}.gtc")
    # Generate .tsv file containing NormR, NormTheta
    #print(f"generating normalized intensity data for {embark_id}")
    marker_normalized_intensity_vals_df = _get_NormR_NormTheta_values_from_gtc(
        gtc_file, bpm_normalization_lookups, bpm_names,
    )
    marker_normalized_intensity_vals_df.reset_index().to_csv(f"{delivery_data_dir}/{genotype_id}_normalized_intensity.tsv", index=False, sep="\t")


def download_idats_and_make_normalized_intensity_files_for_v2_format_delivery(
    delivery_name, delivery_data_dir, cluster_file_s3_path=None, beadpool_manifest_s3_path=None,
):

    # Fetch the sample report .csv from s3 to get dog sentrix ids and positions (required for fetching .idats)
    env_folder = s3.env_folder("prod")
    sample_report_key = (f"{env_folder}unzipped/{delivery_name}/{delivery_name}-SampleReport.csv")
    print("Obtaining Sample Report " + sample_report_key)
    df = s3.fetch_csv(bucket=s3_bucket, key=sample_report_key)
    records = df.to_dict("records")

    # If not provided, fetch the cluster (.egt) and bead pool manifest (.bpm) files used to call genotypes for this delivery
    if cluster_file_s3_path:
        cluster_file_path = os.path.join(delivery_data_dir, cluster_file_s3_path.split("/")[-1])
    else:
        cluster_file_name = f"{str(df['cluster_file'][0])}"
        cluster_file_path = os.path.join(delivery_data_dir, cluster_file_name)
        # this should work for embark_2021-12-23_0609 but doesn't because there's no Embark_2021_260k_20063270_A1_20211123.egt file in this dir - why??
        cluster_file_s3_path = s3.construct_s3_url(bucket=s3_bucket, key=f"{env_folder}Cluster_Files_Updated_Monthly/{cluster_file_name}")
    s3.download_file(cluster_file_s3_path, cluster_file_path)

    if beadpool_manifest_s3_path:
        beadpool_manifest_s3_path = os.path.join(delivery_data_dir, beadpool_manifest_s3_path.split("/")[-1])
    else:
        beadpool_manifest_name = f"{str(df['product'][0])}.bpm"
        beadpool_manifest_path = os.path.join(delivery_data_dir, beadpool_manifest_name)
        beadpool_manifest_s3_path = s3.construct_s3_url(bucket=s3_bucket, key=f"{env_folder}beadpool-manifests/{beadpool_manifest_name}")
    s3.download_file(beadpool_manifest_s3_path, beadpool_manifest_path)

    # Extract normalization lookups and probe names from the .bpm (same for all dogs in delivery)
    manifest = BeadPoolManifest(beadpool_manifest_path)
    bpm_normalization_lookups = manifest.normalization_lookups
    bpm_names = manifest.names

    # For all dogs in the delivery, download .idats, genertate .gtcs, and backcalculate NormR, NormTheta from the .gtcs
    # --> writes 1 .tsv with NormR, NormTheta at all probes for each dog
    # Note: iaap-cli gencall uses a single thread by default (you can specify --num-threads),
    #       so this implementation calls gencall once per dog. It may be more efficient to multithread
    #       a single call on many .idat file pairs; need to investigate.
    _make_normalized_intensity_file_func = functools.partial(
        _make_normalized_intensity_file_from_idats_for_record,
        env_folder, delivery_name, delivery_data_dir, beadpool_manifest_path, cluster_file_path, bpm_normalization_lookups, bpm_names)
    with Pool(POOL_SIZE) as pool:
        pool.map(_make_normalized_intensity_file_func, records)

    # Delete .idats and .gtcs
    #shutil.rmtree(idats_dir_path)
    #shutil.rmtree(gtc_dir_path)


def main(
    delivery_name,
    cluster_file_s3_path,
    beadpool_manifest_s3_path,
):

    # Set up directories for data download and processing
    delivery_data_dir = os.path.join(delivery_name)
    shell.mkdir_p(delivery_data_dir)
    idats_dir_path = os.path.join(delivery_name, "idats")
    shell.mkdir_p(idats_dir_path)
    gtc_dir_path = os.path.join(delivery_name, "gtcs")
    shell.mkdir_p(gtc_dir_path)

    download_idats_and_make_normalized_intensity_files_for_v2_format_delivery(
        delivery_name, delivery_data_dir, cluster_file_s3_path, beadpool_manifest_s3_path,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delivery-name", help="Name of delivery (only v2 format currently supported, e.g. 'embark_YYYY-MM-DD_hhmm'",
    )
    parser.add_argument(
        "--cluster-file-s3-path", help="Path to the cluster file to use on S3.", default=None,
    )
    parser.add_argument(
        "--beadpool-manifest-s3-path", help="Path to the BPM file to use on S3.", default=None,
    )

    args = parser.parse_args()
    main(
        delivery_name=args.delivery_name,
        cluster_file_s3_path=args.cluster_file_s3_path,
        beadpool_manifest_s3_path=args.beadpool_manifest_s3_path,
    )
