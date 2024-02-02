"""Utility functions for tests."""

import os
import subprocess
import tarfile
from contextlib import contextmanager
from glob import glob
from gzip import GzipFile
from io import BytesIO

import nibabel as nb
import numpy as np
import requests
from bids.layout import BIDSLayout
from nipype import logging

LOGGER = logging.getLogger("nipype.utils")


def get_nodes(wf_results):
    """Load nodes from a Nipype workflow's results."""
    return {node.fullname: node for node in wf_results.nodes}


def download_test_data(dset, data_dir=None):
    """Download test data."""
    URLS = {
        "fmriprepwithoutfreesurfer": (
            "https://upenn.box.com/shared/static/seyp1cu9w5v3ds6iink37hlsa217yge1.tar.gz"
        ),
        "nibabies": "https://upenn.box.com/shared/static/rsd7vpny5imv3qkd7kpuvdy9scpnfpe2.tar.gz",
        "ds001419": "https://upenn.box.com/shared/static/yye7ljcdodj9gd6hm2r6yzach1o6xq1d.tar.gz",
        "pnc": "https://upenn.box.com/shared/static/ui2847ys49d82pgn5ewai1mowcmsv2br.tar.gz",
        "ukbiobank": "https://upenn.box.com/shared/static/p5h1eg4p5cd2ef9ehhljlyh1uku0xe97.tar.gz",
    }
    if dset == "*":
        for k in URLS:
            download_test_data(k, data_dir=data_dir)

        return

    if dset not in URLS:
        raise ValueError(f"dset ({dset}) must be one of: {', '.join(URLS.keys())}")

    if not data_dir:
        data_dir = os.path.join(os.path.dirname(get_test_data_path()), "test_data")

    dset_name = dset
    if dset == "ds001419":
        dset_name = "ds001419-fmriprep"

    out_dir = os.path.join(data_dir, dset_name)

    if os.path.isdir(out_dir):
        LOGGER.info(
            f"Dataset {dset} already exists. "
            "If you need to re-download the data, please delete the folder."
        )
        return out_dir
    else:
        LOGGER.info(f"Downloading {dset} to {out_dir}")

    os.makedirs(out_dir, exist_ok=True)
    with requests.get(URLS[dset], stream=True) as req:
        with tarfile.open(fileobj=GzipFile(fileobj=BytesIO(req.content))) as t:
            t.extractall(out_dir)

    return out_dir


def get_test_data_path():
    """Return the path to test datasets, terminated with separator.

    Test-related data are kept in tests folder in "data".
    Based on function by Yaroslav Halchenko used in Neurosynth Python package.
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "data") + os.path.sep)


def check_generated_files(xcpd_dir, output_list_file):
    """Compare files generated by xcp_d with a list of expected files."""
    found_files = sorted(glob(os.path.join(xcpd_dir, "**/*"), recursive=True))
    found_files = [os.path.relpath(f, xcpd_dir) for f in found_files]

    # Ignore figures
    found_files = [f for f in found_files if "figures" not in f]

    with open(output_list_file, "r") as fo:
        expected_files = fo.readlines()
        expected_files = [f.rstrip() for f in expected_files]

    if sorted(found_files) != sorted(expected_files):
        expected_not_found = sorted(list(set(expected_files) - set(found_files)))
        found_not_expected = sorted(list(set(found_files) - set(expected_files)))

        msg = ""
        if expected_not_found:
            msg += "\nExpected but not found:\n\t"
            msg += "\n\t".join(expected_not_found)

        if found_not_expected:
            msg += "\nFound but not expected:\n\t"
            msg += "\n\t".join(found_not_expected)
        raise ValueError(msg)


def check_affines(data_dir, out_dir, input_type):
    """Confirm affines don't change across XCP-D runs."""
    preproc_layout = BIDSLayout(str(data_dir), validate=False, derivatives=False)
    xcp_layout = BIDSLayout(str(out_dir), validate=False, derivatives=False)
    if input_type == "cifti":  # Get the .dtseries.nii
        denoised_files = xcp_layout.get(
            invalid_filters="allow",
            datatype="func",
            extension=".dtseries.nii",
        )
        space = denoised_files[0].get_entities()["space"]
        preproc_files = preproc_layout.get(
            invalid_filters="allow",
            datatype="func",
            space=space,
            extension=".dtseries.nii",
        )

    elif input_type in ("nifti", "ukb"):  # Get the .nii.gz
        # Problem: it's collecting native-space data
        denoised_files = xcp_layout.get(
            datatype="func",
            suffix="bold",
            extension=".nii.gz",
        )
        space = denoised_files[0].get_entities()["space"]
        preproc_files = preproc_layout.get(
            invalid_filters="allow",
            datatype="func",
            space=space,
            suffix="bold",
            extension=".nii.gz",
        )

    else:  # Nibabies
        denoised_files = xcp_layout.get(
            datatype="func",
            space="MNIInfant",
            suffix="bold",
            extension=".nii.gz",
        )
        preproc_files = preproc_layout.get(
            invalid_filters="allow",
            datatype="func",
            space="MNIInfant",
            suffix="bold",
            extension=".nii.gz",
        )

    preproc_file = preproc_files[0].path
    denoised_file = denoised_files[0].path
    img1 = nb.load(preproc_file)
    img2 = nb.load(denoised_file)

    if input_type == "cifti":
        assert img1._nifti_header.get_intent() == img2._nifti_header.get_intent()
        np.testing.assert_array_equal(img1.nifti_header.get_zooms(), img2.nifti_header.get_zooms())
    else:
        np.testing.assert_array_equal(img1.affine, img2.affine)
        if input_type != "ukb":
            # The UK Biobank test dataset has the wrong TR in the header.
            # I'll fix it at some point, but it's not the software's fault.
            np.testing.assert_array_equal(img1.header.get_zooms(), img2.header.get_zooms())


def run_command(command, env=None):
    """Run a given shell command with certain environment variables set."""
    merged_env = os.environ
    if env:
        merged_env.update(env)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        env=merged_env,
    )
    while True:
        line = process.stdout.readline()
        line = str(line, "utf-8")[:-1]
        print(line)
        if line == "" and process.poll() is not None:
            break

    if process.returncode != 0:
        raise Exception(
            f"Non zero return code: {process.returncode}\n" f"{command}\n\n{process.stdout.read()}"
        )


@contextmanager
def chdir(path):
    """Temporarily change directories.

    Taken from https://stackoverflow.com/a/37996581/2589328.
    """
    oldpwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldpwd)


def reorder_expected_outputs():
    """Load each of the expected output files and sort the lines alphabetically.

    This function is called manually by devs when they modify the test outputs.
    """
    test_data_path = get_test_data_path()
    expected_output_files = sorted(glob(os.path.join(test_data_path, "test_*_outputs.txt")))
    for expected_output_file in expected_output_files:
        LOGGER.info(f"Sorting {expected_output_file}")

        with open(expected_output_file, "r") as fo:
            file_contents = fo.readlines()

        file_contents = sorted(list(set(file_contents)))

        with open(expected_output_file, "w") as fo:
            fo.writelines(file_contents)
