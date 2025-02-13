import os


def test_transformer_aws():
    """Run transformer end to end with AWS input data."""
    assert 0 == os.system(
        "poetry run cloudimagedirectory-transformer -f"
        " ${PWD}/tests/transformer/testdata/input/raw/aws/af-south-1.json -op=${PWD} "
        " -dp=${PWD}/tests/transformer/testdata -v output --filter.until=none"
    )
    assert 0 == os.system(
        "diff ${PWD}/tests/transformer/testdata/expected/aws/af-south-1/rhel_6.10_hvm_x86_64_hourly2"
        " ${PWD}/tests/transformer/testdata/output/aws/af-south-1/rhel_6.10_hvm_x86_64_hourly2"
    )
