"""Test image updates from remote cloud APIs."""
from __future__ import annotations

import json

from unittest.mock import patch

import pytest

from jsonschema import ValidationError

from cloudimagedirectory import config
from cloudimagedirectory.update_images import aws
from cloudimagedirectory.update_images import schema


def test_get_regions() -> None:
    """Test AWS region request."""
    with patch("botocore.client.BaseClient._make_api_call") as boto:
        aws.get_regions()

    boto.assert_called_with(
        "DescribeRegions",
        {
            "AllRegions": True,
            "Filters": [
                {"Name": "opt-in-status", "Values": ["opt-in-not-required", "opted-in"]}
            ],
        },
    )


def test_describe_images() -> None:
    """Test AWS image request."""
    with patch("botocore.client.BaseClient._make_api_call") as boto:
        aws.describe_images("us-east-1")

    boto.assert_called_with(
        "DescribeImages",
        {"IncludeDeprecated": False, "Owners": [config.AWS_RHEL_OWNER_ID]},
    )


def test_parse_name_of_all_images() -> None:
    """Test AWS parse image name with real aws data."""
    images = []
    with open("tests/update_images/testdata/aws_list_images.json") as json_file:
        images = json.load(json_file)["Images"]

    for image in images:
        data = aws.parse_image_name(image["Name"])
        assert data["version"]
        assert data["virt"]
        assert data["date"]
        assert data["arch"]
        assert data["release"]
        assert data["billing"]
        assert data["storage"]


def test_get_hourly_images(mock_aws_regions, mock_aws_images):
    """Ensure we filter for hourly images properly."""
    images = aws.get_images(region="us-east-1", image_type="hourly")

    billing_codes = {x["UsageOperation"] for x in images}
    assert billing_codes == {config.AWS_HOURLY_BILLING_CODE}


def test_get_cloud_access_images(mock_aws_regions, mock_aws_images):
    """Ensure we filter for cloud access images properly."""
    images = aws.get_images(region="us-east-1", image_type="cloudaccess")

    billing_codes = {x["UsageOperation"] for x in images}
    assert billing_codes == {config.AWS_CLOUD_ACCESS_BILLING_CODE}


def test_get_images_bogus_type(mock_aws_regions, mock_aws_images):
    """Test the exception if someone provides a bogus image type."""
    with pytest.raises(NotImplementedError):
        aws.get_images(region="us-east-1", image_type="doot")


def test_get_all_images(mock_aws_regions, mock_aws_images) -> None:
    """Test retrieving all AWS hourly images from all regions."""
    images = aws.get_all_images()

    # Regions should be in the keys.
    assert list(images.keys()) == mock_aws_regions.return_value

    # Each region should have only hourly image billing codes.
    for _region, image_list in images.items():
        billing_codes = {x["UsageOperation"] for x in image_list}
        assert billing_codes == {config.AWS_HOURLY_BILLING_CODE}


def test_parse_image_name_basic():
    """Test parsing an AWS image name with a very basic image."""
    image_name = "RHEL-7.9_HVM-20220512-x86_64-1-Hourly2-GP2"
    data = aws.parse_image_name(image_name)

    assert isinstance(data, dict)

    assert not data["intprod"]
    assert not data["extprod"]
    assert data["version"] == "7.9"
    assert data["virt"] == "HVM"
    assert not data["beta"]
    assert data["date"] == "20220512"
    assert data["arch"] == "x86_64"
    assert data["release"] == "1"
    assert data["billing"] == "Hourly2"
    assert data["storage"] == "GP2"


def test_parse_image_name_beta():
    """Test parsing an AWS image name for a beta arm64 image."""
    image_name = "RHEL-9.1.0_HVM_BETA-20220829-arm64-0-Hourly2-GP2"
    data = aws.parse_image_name(image_name)

    assert isinstance(data, dict)

    assert not data["intprod"]
    assert not data["extprod"]
    assert data["version"] == "9.1.0"
    assert data["virt"] == "HVM"
    assert data["beta"] == "BETA"
    assert data["date"] == "20220829"
    assert data["arch"] == "arm64"
    assert data["release"] == "0"
    assert data["billing"] == "Hourly2"
    assert data["storage"] == "GP2"


def test_parse_image_name_internal_product():
    """Test parsing an AWS image name with an internal product."""
    image_name = "RHEL_HA-8.5.0_HVM-20211103-x86_64-0-Hourly2-GP2"
    data = aws.parse_image_name(image_name)

    assert isinstance(data, dict)

    assert data["intprod"] == "HA"
    assert not data["extprod"]
    assert data["version"] == "8.5.0"
    assert data["virt"] == "HVM"
    assert not data["beta"]
    assert data["date"] == "20211103"
    assert data["arch"] == "x86_64"
    assert data["release"] == "0"
    assert data["billing"] == "Hourly2"
    assert data["storage"] == "GP2"


def test_parse_image_name_external_product():
    """Test parsing an AWS image name for a beta arm64 image."""
    image_name = "RHEL-SAP-8.2.0_HVM-20211007-x86_64-0-Hourly2-GP2"
    data = aws.parse_image_name(image_name)

    assert isinstance(data, dict)

    assert not data["intprod"]
    assert data["extprod"] == "SAP"
    assert data["version"] == "8.2.0"
    assert data["virt"] == "HVM"
    assert not data["beta"]
    assert data["date"] == "20211007"
    assert data["arch"] == "x86_64"
    assert data["release"] == "0"
    assert data["billing"] == "Hourly2"
    assert data["storage"] == "GP2"


def test_parse_invalid_image_name():
    """Test parsing an AWS invalid image name."""
    image_name = "thisisnotarealname"
    data = aws.parse_image_name(image_name)

    assert not data


def test_format_image():
    """Test transforming a single AWS image into a schema approved format."""
    mocked_image = {
        "Architecture": "x86_64",
        "CreationDate": "2021-02-10T16:19:48.000Z",
        "ImageId": "ami-0bcadaece3162039d",
        "Name": "RHEL-8.3_HVM-20210209-x86_64-0-Hourly2-GP2",
        "VirtualizationType": "hvm",
    }

    data = {"images": {"aws": [aws.format_image(mocked_image, "us-east-1")]}}

    try:
        schema.validate_json(data)
    except ValidationError as exc:
        raise AssertionError(f"Formatted data does not expect schema: {exc}")


def test_format_all_images(mock_aws_regions, mock_aws_images):
    """Test transforming a list of AWS images into a schema approved format."""
    data = aws.format_all_images()

    try:
        schema.validate_json(data)
    except ValidationError as exc:
        raise AssertionError(f"Formatted data does not expect schema: {exc}")
