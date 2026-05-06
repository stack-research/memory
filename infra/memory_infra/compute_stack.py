from __future__ import annotations

from pathlib import Path

from aws_cdk import Duration, Stack, aws_apigateway as apigw
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_glue as glue
from aws_cdk import aws_athena as athena
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from constructs import Construct

from .config import InfraConfig


class MemoryComputeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cfg: InfraConfig,
        events_bucket: s3.IBucket,
        state_bucket: s3.IBucket,
        analytics_bucket: s3.IBucket,
        vector_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repo_root = Path(__file__).resolve().parents[2]
        lambda_code_path = str(repo_root)

        env = {
            "AWS_PROFILE": cfg.aws_profile,
            "AWS_EVENTS_BUCKET_NAME": events_bucket.bucket_name,
            "AWS_STATE_BUCKET_NAME": state_bucket.bucket_name,
            "AWS_ANALYTICS_BUCKET_NAME": analytics_bucket.bucket_name,
            "AWS_VECTOR_BUCKET_NAME": vector_bucket.bucket_name,
            "AWS_VECTOR_INDEX_NAME": cfg.vector_index_name,
            "MEMORY_ROOT": "/tmp/memory-lab",
            "PYTHONPATH": "/var/task/src",
        }

        lambda_asset = _lambda.Code.from_asset(
            lambda_code_path,
            exclude=[
                "infra/**",
                ".venv/**",
                "var/**",
                "tests/**",
                ".git/**",
                "__pycache__/**",
            ],
        )

        self.api_lambda = _lambda.Function(
            self,
            "MemoryApiLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="src.memory_lab.handlers.api_handler.handler",
            code=lambda_asset,
            timeout=Duration.seconds(30),
            environment=env,
        )

        self.sleep_lambda = _lambda.Function(
            self,
            "MemorySleepLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="src.memory_lab.handlers.sleep_handler.handler",
            code=lambda_asset,
            timeout=Duration.minutes(2),
            environment=env,
        )

        events_bucket.grant_read_write(self.api_lambda)
        state_bucket.grant_read_write(self.api_lambda)
        vector_bucket.grant_read_write(self.api_lambda)

        events_bucket.grant_read_write(self.sleep_lambda)
        state_bucket.grant_read_write(self.sleep_lambda)
        analytics_bucket.grant_read_write(self.sleep_lambda)
        vector_bucket.grant_read_write(self.sleep_lambda)

        glue_db = glue.CfnDatabase(
            self,
            "MemoryGlueDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="memory_lab",
                description="Memory lab analytics catalog",
            ),
        )
        athena.CfnWorkGroup(
            self,
            "MemoryAthenaWorkgroup",
            name="memory_lab_wg",
            recursive_delete_option=True,
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{analytics_bucket.bucket_name}/athena-results/"
                )
            ),
        ).add_dependency(glue_db)

        self.api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["glue:GetDatabase", "glue:GetTable", "athena:StartQueryExecution"],
                resources=["*"],
            )
        )
        self.sleep_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["glue:GetDatabase", "glue:GetTable", "athena:StartQueryExecution"],
                resources=["*"],
            )
        )

        api = apigw.RestApi(self, "MemoryApi", rest_api_name="memory-lab-api")
        v1 = api.root.add_resource("v1")
        events_resource = v1.add_resource("events")
        retrieve_resource = v1.add_resource("retrieve")
        beliefs_resource = v1.add_resource("beliefs").add_resource("current")
        memory_resource = v1.add_resource("memory").add_resource("{id}").add_resource("lineage")

        integration = apigw.LambdaIntegration(self.api_lambda)
        events_resource.add_method("POST", integration)
        retrieve_resource.add_method("POST", integration)
        beliefs_resource.add_method("GET", integration)
        memory_resource.add_method("GET", integration)

        rule = events.Rule(
            self,
            "SleepScheduleRule",
            schedule=events.Schedule.rate(Duration.minutes(15)),
        )
        rule.add_target(targets.LambdaFunction(self.sleep_lambda))
