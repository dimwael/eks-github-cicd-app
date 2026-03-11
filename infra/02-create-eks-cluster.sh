#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="eks-github-cicd-app"
REGION="us-east-1"

echo "Creating EKS cluster: $CLUSTER_NAME"
eksctl create cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --version 1.30 \
  --nodegroup-name standard-nodes \
  --node-type t3.medium \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 4 \
  --managed

echo "Associating IAM OIDC provider..."
eksctl utils associate-iam-oidc-provider \
  --cluster "$CLUSTER_NAME" \
  --region "$REGION" \
  --approve

echo "Cluster ready."
