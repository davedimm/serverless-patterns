#!/usr/bin/env python3
import os

from aws_cdk import core as cdk
from aws_cdk import (
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_glue as glue,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
    core
)

# For consistency with TypeScript code, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import core

class SfnGlueCdkStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Glue job execution IAM Role      
        glue_job_role = iam.Role(
            self,
            'Glue-Job-Role',
            assumed_by=iam.ServicePrincipal('glue.amazonaws.com'),
            managed_policies = [iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSGlueServiceRole')]
        )
        
        
        S3_BUCKET_NAME = "MyCdkGlueJobBucket"

        # S3 Bucket to host glue scripts
        bucket = s3.Bucket(self, S3_BUCKET_NAME, versioned=True,removal_policy=core.RemovalPolicy.DESTROY,
                    auto_delete_objects=True, block_public_access=s3.BlockPublicAccess.BLOCK_ALL)

        # asset to sync local scripts folder with S3 bucket
        asset = s3deploy.Source.asset("./resources/glue-scripts")       

        # Sync local scripts with S3 bucket
        s3deploy.BucketDeployment(self, "DeployGlueJobScripts",
            sources=[asset],
            destination_bucket=bucket,
            destination_key_prefix="glue-python-scripts"
            )
        
        # Grant read write access for glue execution IAM role for S3 bucket
        bucket.grant_read_write(glue_job_role)
        
        scriptLocation = 's3://'+bucket.bucket_name+'/glue-python-scripts/hello.py'
        
        # Python-shell Glue job
        job = glue.CfnJob(self,'Glue-job', name = 'cdk-test-glue-python-job',
            role=glue_job_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name='pythonshell',
                python_version='3',
                script_location=scriptLocation
            ))

        # Glue Start Job Run Task for State Function (integration_pattern = .sync)
        glue_task = sfn_tasks.GlueStartJobRun(self, "Task",
            glue_job_name=job.name,
            integration_pattern = sfn.IntegrationPattern.RUN_JOB,
            arguments=sfn.TaskInput.from_object({
                "--message": sfn.JsonPath.string_at("$.message")
            }),
            timeout=core.Duration.minutes(6),
            notify_delay_after= core.Duration.minutes(6)
        )

        # State Function defination
        definition = glue_task
        state_machine = sfn.StateMachine(
            self, "GlueJobStateMachine",
            definition=definition,
            timeout=core.Duration.minutes(10)
        )

        # CDK Outputs
        core.CfnOutput(scope=self, id='StateMachineArn', value=state_machine.state_machine_arn)
        core.CfnOutput(scope=self, id='GlueJobName', value=job.name)
        core.CfnOutput(scope=self, id='S3BucketName', value=bucket.bucket_name)
        
app = core.App()
SfnGlueCdkStack(app,"SfnGlueCdkExample")
app.synth()
