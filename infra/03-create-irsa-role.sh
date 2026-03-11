#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="eks-github-cicd-app"
REGION="us-east-1"
ACCOUNT_ID="649976227195"
NAMESPACE="default"
SERVICE_ACCOUNT="eks-github-cicd-app"
REPO_NAME="eks-github-cicd-app"

echo "Creating IRSA role for ECR pull access..."
eksctl create iamserviceaccount \
  --cluster "$CLUSTER_NAME" \
  --region "$REGION" \
  --namespace "$NAMESPACE" \
  --name "$SERVICE_ACCOUNT" \
  --attach-policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly \
  --approve \
  --override-existing-serviceaccounts

ROLE_ARN=$(aws iam get-role \
  --role-name "eksctl-${CLUSTER_NAME}-addon-iamserviceaccount-${NAMESPACE}-${SERVICE_ACCOUNT}-Role1" \
  --query 'Role.Arn' --output text 2>/dev/null || \
  eksctl get iamserviceaccount \
    --cluster "$CLUSTER_NAME" \
    --region "$REGION" \
    --namespace "$NAMESPACE" \
    --name "$SERVICE_ACCOUNT" \
    -o json | python3 -c "import sys,json; data=json.load(sys.stdin); print(data[0]['status']['roleARN'])")

echo ""
echo "IRSA Role ARN: $ROLE_ARN"
echo ""
echo "Add this to helm/eks-github-cicd-app/values.yaml:"
echo "serviceAccount:"
echo "  annotations:"
echo "    eks.amazonaws.com/role-arn: \"$ROLE_ARN\""
