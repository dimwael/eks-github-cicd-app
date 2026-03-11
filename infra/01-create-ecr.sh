#!/usr/bin/env bash
set -euo pipefail

ACCOUNT_ID="649976227195"
REGION="us-east-1"
REPO_NAME="eks-github-cicd-app"

echo "Creating ECR repository: $REPO_NAME"
aws ecr create-repository \
  --repository-name "$REPO_NAME" \
  --region "$REGION" \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256 2>/dev/null || echo "Repository already exists"

ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"
echo "ECR URI: $ECR_URI"
