from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import (
    CfnResource,
    CfnOutput,
    RemovalPolicy,
    Stack,
    aws_s3 as s3,
    aws_ssm as ssm,
)
from constructs import Construct

from .config import InfraConfig


@dataclass(slots=True)
class DataStackOutputs:
    events_bucket: s3.Bucket
    state_bucket: s3.Bucket
    analytics_bucket: s3.Bucket
    vector_bucket_name: str
    vector_index_name: str


class MemoryDataStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, cfg: InfraConfig, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.cfg = cfg

        self.events_bucket = self._secure_bucket("EventsBucket", cfg.events_bucket_name)
        self.state_bucket = self._secure_bucket("StateBucket", cfg.state_bucket_name)
        self.analytics_bucket = self._secure_bucket("AnalyticsBucket", cfg.analytics_bucket_name)
        self.vector_bucket = CfnResource(
            self,
            "VectorBucket",
            type="AWS::S3Vectors::VectorBucket",
            properties={"VectorBucketName": cfg.vector_bucket_name},
        )
        self.vector_index = CfnResource(
            self,
            "VectorIndex",
            type="AWS::S3Vectors::Index",
            properties={
                "VectorBucketName": cfg.vector_bucket_name,
                "IndexName": cfg.vector_index_name,
                "DataType": "float32",
                "Dimension": 16,
                "DistanceMetric": "cosine",
                "MetadataConfiguration": {"NonFilterableMetadataKeys": []},
            },
        )
        self.vector_index.add_dependency(self.vector_bucket)

        self._put_param("/memory/events_bucket_name", self.events_bucket.bucket_name)
        self._put_param("/memory/state_bucket_name", self.state_bucket.bucket_name)
        self._put_param("/memory/analytics_bucket_name", self.analytics_bucket.bucket_name)
        self._put_param("/memory/vector_bucket_name", cfg.vector_bucket_name)
        self._put_param("/memory/vector_index_name", cfg.vector_index_name)

        CfnOutput(self, "EventsBucketName", value=self.events_bucket.bucket_name)
        CfnOutput(self, "StateBucketName", value=self.state_bucket.bucket_name)
        CfnOutput(self, "AnalyticsBucketName", value=self.analytics_bucket.bucket_name)
        CfnOutput(self, "VectorBucketName", value=cfg.vector_bucket_name)
        CfnOutput(self, "VectorIndexName", value=cfg.vector_index_name)

    def _secure_bucket(self, sid: str, bucket_name: str) -> s3.Bucket:
        return s3.Bucket(
            self,
            sid,
            bucket_name=bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            auto_delete_objects=False,
        )

    def _put_param(self, name: str, value: str) -> None:
        ssm.StringParameter(
            self,
            f"Param{name.replace('/', '_')}",
            parameter_name=name,
            string_value=value,
        )
