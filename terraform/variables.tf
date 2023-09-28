variable "region" {
  description = "The AWS region to create resources in."
  default     = "us-east-2"
}

variable "env_type" {
  description = "environment for resources"
  default     = "prod"
}
