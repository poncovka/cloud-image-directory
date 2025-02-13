"""Transforms the raw data into useful data."""
import os

from datetime import datetime
from typing import Callable

from cloudimagedirectory import config
from cloudimagedirectory.connection import connection
from cloudimagedirectory.format import format_aws
from cloudimagedirectory.format import format_azure
from cloudimagedirectory.format import format_google


class Pipeline:
    """Builds a pipeline of transformer tasks."""

    transformers: list[Callable] = []
    filter_funcs: list[Callable] = []
    idx_generators: list[Callable] = []

    def __init__(
        self,
        src_conn,
        transformer_funcs: list[Callable],
        filter_funcs: list[Callable],
        idx_generator_funcs: list[Callable],
    ):
        """Initialize the pipeline."""
        self.src_conn = src_conn
        self.filter_funcs = filter_funcs
        for transformer_func in transformer_funcs:
            self.transformers.append(transformer_func(self.src_conn))
        for idx_generator_func in idx_generator_funcs:
            self.idx_generators.append(idx_generator_func(self.src_conn))

    def run(self, data):
        """Run the pipeline."""
        results = data
        for transformer in self.transformers:
            results.extend(transformer.run(results))

        generated_pages = len(results)
        print("total images: ", generated_pages)

        for filter_func in self.filter_funcs:
            before = generated_pages
            results = filter_func(results)
            after = len(results)
            if before != after:
                print(f"filtered {before - after} items")

        generated_pages = len(results)

        for idx_generator in self.idx_generators:
            results.extend(idx_generator.run(results))

        print(f"generated indexes: {len(results) - generated_pages}")

        return results


class Transformer:
    """Base class for transforming raw image data."""

    def __init__(self, src_conn):
        """Initialize the transformer."""
        self.src_conn = src_conn

    def run(self, data):
        """Transform the raw data."""
        raise NotImplementedError


class TransformerIdxListImageLatest(Transformer):
    """Sort the transformed data, to have the latest images."""

    chunk_size = 50
    provider = ""

    def run(self, data):
        """Sort the raw data."""
        # NOTE: Verify that the data is not raw.
        entries = [x for x in data if not x.is_raw() and not x.is_provided_by("idx")]

        # NOTE: Sort the list of data by date
        entries.sort(
            key=lambda x: datetime.strptime(
                "".join(x.content["date"].split("T")[0]), "%Y-%m-%d"
            ),
            reverse=True,
        )

        list = []
        for entry in entries:
            provider = "unknown"
            if entry.is_provided_by("aws"):
                provider = "aws"
            elif entry.is_provided_by("azure"):
                provider = "azure"
            elif entry.is_provided_by("google"):
                provider = "google"

            # NOTE: Filter images for pre-defined provider.
            # If Provider is not set, all providers are valid.
            if self.provider != "" and self.provider != provider:
                continue

            region = "unkown"
            filename = entry.filename.split("/")
            if len(filename) == 3:
                region = filename[1]
            else:
                print("warn: could not determine region of image: " + entry.filename)

            list.append(
                {
                    "name": entry.content["name"],
                    "date": entry.content["date"].split("T")[0],
                    "provider": provider,  # TODO: Evaluate if this can be removed
                    "ref": entry.filename,
                    "arch": entry.content["arch"],
                    "region": region,  # TODO: Evaluate if this can be removed
                }
            )

        # NOTE: Split the list of images into equally sized chunkes
        chunked_list = []
        chunk = []
        for i, item in enumerate(list, 1):
            chunk.append(item)
            if len(list) == i or i % self.chunk_size == 0:
                chunked_list.append(chunk)
                chunk = []

        provider = ""
        if self.provider != "":
            provider = "-" + self.provider

        first = 0
        results = []
        for page in range(first, len(chunked_list)):
            data_entry = connection.DataEntry(
                f"idx/list/sort-by-date{provider}/{page}", chunked_list[page]
            )
            results.append(data_entry)

        page_entry = connection.DataEntry(
            f"idx/list/sort-by-date{provider}/pages",
            {
                "first": first,
                "last": len(chunked_list) - 1,
                "entries": self.chunk_size,
            },
        )
        results.append(page_entry)

        return results


class TransformerIdxListImageLatestGoogle(TransformerIdxListImageLatest):
    """Sort the transformed data to have the latest google images."""

    def run(self, data):
        self.provider = "google"
        return super().run(data)


class TransformerIdxListImageLatestAWS(TransformerIdxListImageLatest):
    """Sort the transformed data to have the latest AWS images."""

    def run(self, data):
        self.provider = "aws"
        return super().run(data)


class TransformerIdxListImageLatestAZURE(TransformerIdxListImageLatest):
    """Sort the transformed data to have the latest AZURE images."""

    def run(self, data):
        self.provider = "azure"
        return super().run(data)


class TransformerAWS(Transformer):
    """Transform raw AWS data."""

    def run(self, data):
        """Transform the raw data."""
        # NOTE: Verify that the data is from AWS.
        entries = [x for x in data if x.is_provided_by("aws") and x.is_raw()]

        results = []
        for entry in entries:
            raw = self.src_conn.get_content(entry)
            region = os.path.basename(raw.filename).split(".")[0]

            for content in raw.content:
                if content["OwnerId"] != config.AWS_RHEL_OWNER_ID:
                    continue

                image_data = format_aws.image_rhel(content, region)
                image_name = image_data["name"].replace(" ", "_").lower()
                data_entry = connection.DataEntry(
                    f"aws/{region}/{image_name}", image_data
                )
                results.append(data_entry)

        return results


class TransformerGoogle(Transformer):
    """Transform raw google data."""

    def run(self, data):
        """Transform the raw data."""
        entries = [x for x in data if x.is_provided_by("google") and x.is_raw()]

        results = []
        for entry in entries:
            raw = self.src_conn.get_content(entry)
            for content in raw.content:
                content["creation_timestamp"] = content["creationTimestamp"]
                if "rhel" in content["name"]:
                    image_data = format_google.image_rhel(content)
                    image_name = image_data["name"].replace(" ", "_").lower()
                    data_entry = connection.DataEntry(
                        f"google/global/{image_name}", image_data
                    )
                    results.append(data_entry)

        return results


class TransformerAZURE(Transformer):
    """Transform raw Azure data."""

    def run(self, data):
        """Transform the raw data."""
        # NOTE: Verify that the data is from Azure.
        entries = [x for x in data if x.is_provided_by("azure") and x.is_raw()]

        results = []
        for entry in entries:
            raw = self.src_conn.get_content(entry)
            region = os.path.basename(raw.filename).split(".")[0]

            for content in raw.content:
                if content["publisher"] != "RedHat":
                    continue

                content["hyperVGeneration"] = "unknown"

                try:
                    image_data = format_azure.image_rhel(content)
                    image_name = image_data["name"].replace(" ", "_").lower()
                    data_entry = connection.DataEntry(
                        f"azure/{region}/{image_name}", image_data
                    )

                    results.append(data_entry)
                except:
                    print(
                        "Could not format image, sku: "
                        + content["sku"]
                        + " offer: "
                        + content["offer"]
                    )

        return results


class TransformerIdxListImageNames(Transformer):
    """Genearate list of all image names."""

    def run(self, data):
        """Sort the raw data."""
        # NOTE: Verify that the data is not raw.
        entries = [x for x in data if not x.is_raw() and not x.is_provided_by("idx")]

        results = []

        for entry in entries:
            results.append(entry.filename)

        results.sort()

        return [connection.DataEntry("idx/list/image-names", results)]
