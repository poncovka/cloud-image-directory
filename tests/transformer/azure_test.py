import os


def test_transformer_azure():
    """Run transformer end to end with Azure input data."""
    assert 0 == os.system(
        "poetry run cloudimagedirectory-transformer -f"
        " ${PWD}/tests/transformer/testdata/input/raw/azure/eastus.json -op=${PWD} "
        " -dp=${PWD}/tests/transformer/testdata -v output --filter.until=none"
    )
    assert 0 == os.system(
        "diff ${PWD}/tests/transformer/testdata/expected/azure/eastus/osa_osa_311_x64"
        " ${PWD}/tests/transformer/testdata/output/azure/eastus/osa_osa_311_x64"
    )
