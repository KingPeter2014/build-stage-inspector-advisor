terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
  # Remote state in S3 + DynamoDB locking.
  # Initialise with:
  #   terraform init \
  #     -backend-config="bucket=<tfstate-bucket>" \
  #     -backend-config="key=${var.project}/${var.env}/terraform.tfstate" \
  #     -backend-config="region=${var.aws_region}" \
  #     -backend-config="dynamodb_table=terraform-locks"
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = merge(var.tags, {
      project     = var.project
      environment = var.env
      managed_by  = "terraform"
    })
  }
}

locals {
  prefix = "${var.project}-${var.env}"
  # Availability zones — use first two in the region
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

data "aws_availability_zones" "available" {
  state = "available"
}

# ── VPC ───────────────────────────────────────────────────────────────────────

resource "aws_vpc" "llmops" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.llmops.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone = local.azs[count.index]
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.llmops.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index + 4)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true
}

resource "aws_internet_gateway" "llmops" {
  vpc_id = aws_vpc.llmops.id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.llmops.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.llmops.id
  }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "llmops" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  depends_on    = [aws_internet_gateway.llmops]
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.llmops.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.llmops.id
  }
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# ── Security groups ───────────────────────────────────────────────────────────

resource "aws_security_group" "alb" {
  name        = "${local.prefix}-alb-sg"
  description = "Allow HTTPS inbound from internet"
  vpc_id      = aws_vpc.llmops.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs" {
  name        = "${local.prefix}-ecs-sg"
  description = "Allow traffic from ALB to ECS tasks"
  vpc_id      = aws_vpc.llmops.id

  ingress {
    from_port       = 4002
    to_port         = 4002
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "opensearch" {
  name        = "${local.prefix}-opensearch-sg"
  description = "Allow access from ECS tasks"
  vpc_id      = aws_vpc.llmops.id

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
}

resource "aws_security_group" "redis" {
  name        = "${local.prefix}-redis-sg"
  description = "Allow Redis from ECS tasks"
  vpc_id      = aws_vpc.llmops.id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
}

# ── ECR repository ────────────────────────────────────────────────────────────

resource "aws_ecr_repository" "gateway" {
  name                 = "${local.prefix}-gateway"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "gateway" {
  repository = aws_ecr_repository.gateway.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

# ── Amazon OpenSearch Service ─────────────────────────────────────────────────

resource "aws_opensearch_domain" "llmops" {
  domain_name    = "${local.prefix}-os"
  engine_version = "OpenSearch_2.13"

  cluster_config {
    instance_type  = var.opensearch_instance_type
    instance_count = var.opensearch_instance_count
  }

  ebs_options {
    ebs_enabled = true
    volume_size = var.opensearch_volume_size_gb
  }

  vpc_options {
    subnet_ids         = [aws_subnet.private[0].id]
    security_group_ids = [aws_security_group.opensearch.id]
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https = true
  }

  advanced_security_options {
    enabled                        = true
    internal_user_database_enabled = false

    master_user_options {
      master_user_arn = aws_iam_role.ecs_task.arn
    }
  }
}

resource "aws_opensearch_domain_policy" "llmops" {
  domain_name = aws_opensearch_domain.llmops.domain_name
  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = aws_iam_role.ecs_task.arn }
      Action    = "es:*"
      Resource  = "${aws_opensearch_domain.llmops.arn}/*"
    }]
  })
}

# ── ElastiCache (Redis) ───────────────────────────────────────────────────────

resource "aws_elasticache_subnet_group" "llmops" {
  name       = "${local.prefix}-redis-subnet"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_cluster" "llmops" {
  cluster_id           = "${local.prefix}-redis"
  engine               = "redis"
  node_type            = var.elasticache_node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.1"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.llmops.name
  security_group_ids   = [aws_security_group.redis.id]
}

# ── S3 bucket (raw docs + model artifacts) ───────────────────────────────────

resource "aws_s3_bucket" "llmops" {
  bucket = "${local.prefix}-data-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "llmops" {
  bucket = aws_s3_bucket.llmops.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "llmops" {
  bucket = aws_s3_bucket.llmops.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "llmops" {
  bucket                  = aws_s3_bucket.llmops.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_caller_identity" "current" {}

# ── IAM role for ECS task (Bedrock + OpenSearch + S3 + CloudWatch) ────────────

resource "aws_iam_role" "ecs_task" {
  name = "${local.prefix}-ecs-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task" {
  name = "${local.prefix}-ecs-task-policy"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "BedrockInference"
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:InvokeAgent"]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/*"
      },
      {
        Sid      = "S3Access"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.llmops.arn, "${aws_s3_bucket.llmops.arn}/*"]
      },
      {
        Sid      = "CloudWatchLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/ecs/${local.prefix}*"
      },
      {
        Sid      = "SecretsManager"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${local.prefix}/*"
      }
    ]
  })
}

resource "aws_iam_role" "ecs_execution" {
  name = "${local.prefix}-ecs-exec-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_ecr" {
  name = "${local.prefix}-ecr-pull"
  role = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ecr:GetAuthorizationToken", "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"]
      Resource = "*"
    }]
  })
}

# ── CloudWatch log group ──────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "gateway" {
  name              = "/ecs/${local.prefix}-gateway"
  retention_in_days = var.env == "production" ? 90 : 14
}

# ── ECS Cluster + Fargate service ─────────────────────────────────────────────

resource "aws_ecs_cluster" "llmops" {
  name = "${local.prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_task_definition" "gateway" {
  family                   = "${local.prefix}-gateway"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory_mb
  task_role_arn            = aws_iam_role.ecs_task.arn
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([{
    name      = "gateway"
    image     = var.gateway_image
    essential = true
    portMappings = [{ containerPort = 4002, protocol = "tcp" }]
    environment = [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "BEDROCK_MODEL_ID", value = var.bedrock_model_id },
      { name = "OPENSEARCH_ENDPOINT", value = "https://${aws_opensearch_domain.llmops.endpoint}" },
      { name = "REDIS_URL", value = "redis://${aws_elasticache_cluster.llmops.cache_nodes[0].address}:6379" },
      { name = "S3_BUCKET_NAME", value = aws_s3_bucket.llmops.bucket }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.gateway.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "gateway"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:4002/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 10
    }
  }])
}

resource "aws_ecs_service" "gateway" {
  name            = "${local.prefix}-gateway"
  cluster         = aws_ecs_cluster.llmops.id
  task_definition = aws_ecs_task_definition.gateway.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.gateway.arn
    container_name   = "gateway"
    container_port   = 4002
  }

  depends_on = [aws_lb_listener.https]
}

# ── Application Load Balancer ─────────────────────────────────────────────────

resource "aws_lb" "llmops" {
  name               = "${local.prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

resource "aws_lb_target_group" "gateway" {
  name        = "${local.prefix}-gateway-tg"
  port        = 4002
  protocol    = "HTTP"
  vpc_id      = aws_vpc.llmops.id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.llmops.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.gateway.arn
  }
}
