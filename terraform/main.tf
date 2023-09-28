provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Environment = "${var.env_type}"
      Owner       = "ops"
      Application = "managed-policies"
    }
  }
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }

  backend "s3" {
    bucket = "<app-infra-bucket>"
    region = "us-east-2"
    key    = "us-east-2/managed-policies/terraform.tfstate"
  }
}

data "aws_caller_identity" "current" {}

module "s3_bucket" {
  source = "terraform-aws-modules/s3-bucket/aws"

  bucket                   = "<managed-policies-bucket-name>"
  acl                      = "private"
  control_object_ownership = true
  object_ownership         = "ObjectWriter"
  versioning = {
    enabled = true
  }

}

resource "aws_s3_bucket_object" "s3_tenant_policy" {
  bucket = module.s3_bucket.s3_bucket_id
  key    = "s3_tenant_policy.json"
  source = "policies/s3_tenant_policy.json"
}


