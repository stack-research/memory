import os

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_athena as athena
from aws_cdk import aws_glue as glue
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3tables as s3tables
from aws_cdk import aws_s3vectors as s3vectors
from constructs import Construct


class MemoryLabStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vector_bucket_name = os.environ.get("AWS_S3_VECTOR_BUCKET_NAME")
        if not vector_bucket_name:
            raise ValueError("AWS_S3_VECTOR_BUCKET_NAME must be set")

        table_bucket_name = os.environ.get("AWS_S3_TABLE_BUCKET_NAME")
        if not table_bucket_name:
            raise ValueError("AWS_S3_TABLE_BUCKET_NAME must be set")

        table_name = os.environ.get("AWS_S3_TABLE_NAME", "memory_events_v4")
        table_namespace = os.environ.get("AWS_S3_TABLE_NAMESPACE", "memory_lab")

        ingress_bucket_name = os.environ.get("AWS_S3_LINEAGE_INGRESS_BUCKET_NAME")
        if not ingress_bucket_name:
            raise ValueError("AWS_S3_LINEAGE_INGRESS_BUCKET_NAME must be set")

        athena_workgroup_name = os.environ.get("AWS_ATHENA_WORKGROUP_NAME", "memory-lab")
        athena_database_name = os.environ.get("AWS_ATHENA_DATABASE", "memory_lab")

        index_name = os.environ.get("AWS_S3_VECTOR_INDEX_NAME", "memories-v1")
        index_dimension = int(os.environ.get("AWS_S3_VECTOR_INDEX_DIMENSION", "1536"))

        # S3 Vector buckets are private by default (no public access configuration).
        vector_bucket = s3vectors.CfnVectorBucket(
            self,
            "RecallVectorBucket",
            vector_bucket_name=vector_bucket_name,
        )

        # Create a vector index for the vector bucket.
        vector_index = s3vectors.CfnIndex(
            self,
            "RecallVectorIndex",
            vector_bucket_name=vector_bucket_name,
            index_name=index_name,
            data_type="float32",
            dimension=index_dimension,
            distance_metric="cosine",
        )
        vector_index.add_dependency(vector_bucket)

        # Create a table bucket for the lineage table.
        table_bucket = s3tables.CfnTableBucket(
            self,
            "LineageTableBucket",
            table_bucket_name=table_bucket_name,
        )

        # Create a namespace for the lineage table.
        lineage_namespace = s3tables.CfnNamespace(
            self,
            "LineageNamespace",
            table_bucket_arn=table_bucket.attr_table_bucket_arn,
            namespace=table_namespace,
        )
        lineage_namespace.add_dependency(table_bucket)

        # Create a table for the lineage table.
        lineage_table = s3tables.CfnTable(
            self,
            "LineageTable",
            table_bucket_arn=table_bucket.attr_table_bucket_arn,
            namespace=table_namespace,
            table_name=table_name,
            open_table_format="ICEBERG",
            iceberg_metadata=s3tables.CfnTable.IcebergMetadataProperty(
                iceberg_schema=s3tables.CfnTable.IcebergSchemaProperty(
                    schema_field_list=[
                        s3tables.CfnTable.SchemaFieldProperty(name="event_id", type="string", required=True),
                        s3tables.CfnTable.SchemaFieldProperty(name="agent_id", type="string", required=True),
                        s3tables.CfnTable.SchemaFieldProperty(name="stream_id", type="string", required=True),
                        s3tables.CfnTable.SchemaFieldProperty(name="event_type", type="string", required=True),
                        s3tables.CfnTable.SchemaFieldProperty(name="memory_id", type="string", required=True),
                        s3tables.CfnTable.SchemaFieldProperty(name="payload", type="string", required=False),
                        s3tables.CfnTable.SchemaFieldProperty(name="actor_class", type="string", required=True),
                        s3tables.CfnTable.SchemaFieldProperty(name="source_class", type="string", required=True),
                        s3tables.CfnTable.SchemaFieldProperty(name="event_time", type="timestamp", required=True),
                        s3tables.CfnTable.SchemaFieldProperty(name="schema_version", type="string", required=True),
                        s3tables.CfnTable.SchemaFieldProperty(name="parent_event_id", type="string", required=False),
                    ]
                ),
                table_properties={"format-version": "2"},
            ),
        )
        lineage_table.add_dependency(lineage_namespace)

        # This is a temporary simplification for v0 labs.
        # TODO: remove this bucket and tighten the canonical write path directly into S3 Tables-managed lineage.
        ingress_bucket = s3.Bucket(
            self,
            "LineageIngressBucket",
            bucket_name=ingress_bucket_name,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Create a results bucket for the Athena queries.
        athena_results_bucket = s3.Bucket(
            self,
            "AthenaResultsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Create a database for the Athena queries.
        glue_db = glue.CfnDatabase(
            self,
            "MemoryLabAthenaDatabase",
            catalog_id=Stack.of(self).account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=athena_database_name,
                description="Memory lab Athena staging and ingestion database",
            ),
        )

        # Create a workgroup for the Athena queries.
        athena_workgroup = athena.CfnWorkGroup(
            self,
            "MemoryLabAthenaWorkgroup",
            name=athena_workgroup_name,
            state="ENABLED",
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                enforce_work_group_configuration=True,
                publish_cloud_watch_metrics_enabled=True,
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{athena_results_bucket.bucket_name}/queries/"
                ),
            ),
        )
        athena_workgroup.node.add_dependency(glue_db)
        athena_workgroup.node.add_dependency(ingress_bucket)
