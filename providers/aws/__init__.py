"""
providers/aws — AWS AgentCore LLMOps stack.

Stack:
  LLM Gateway        Amazon Bedrock Runtime (boto3)
  Vector Store       Amazon OpenSearch Service (opensearch-py)
  Data Lake          Amazon S3 (boto3)
  Feature Store      Amazon SageMaker Feature Store (sagemaker)
  Experiment Track.  Amazon SageMaker Experiments (sagemaker)
  Model Registry     Amazon SageMaker Model Registry (sagemaker)
  Single Agent       AWS AgentCore / Bedrock Agents (boto3 bedrock-agent-runtime)
  Multi-Agent        AWS AgentCore multi-agent supervisor
  Observability      Amazon CloudWatch Metrics + AWS X-Ray (boto3 / aws-xray-sdk)
  ETL                AWS Glue (boto3 glue)
  Guardrails         Amazon Bedrock Guardrails (boto3 bedrock)
  Auth               AWS IAM + Amazon Cognito
  Caching            Amazon ElastiCache for Redis (REDIS_URL env var)
"""

PROVIDER_NAME = "aws"
