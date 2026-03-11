#!/usr/bin/env bash
set -euo pipefail

ACCOUNT_ID="649976227195"
REGION="us-east-1"
GITHUB_ORG="dimwael"
REPO_NAME="eks-github-cicd-app"
ROLE_NAME="github-actions-eks-github-cicd-app"
CLUSTER_NAME="eks-github-cicd-app"

echo "Creating GitHub Actions OIDC IAM role..."

# Create OIDC provider if it doesn't exist
OIDC_PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" \
  --region "$REGION" 2>/dev/null || echo "OIDC provider already exists"

# Trust policy
TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${OIDC_PROVIDER_ARN}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/${REPO_NAME}:*"
        }
      }
    }
  ]
}
EOF
)

aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document "$TRUST_POLICY" 2>/dev/null || echo "Role already exists, updating trust policy..."

aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

# Inline policy for EKS access
EKS_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster",
        "eks:ListClusters"
      ],
      "Resource": "arn:aws:eks:${REGION}:${ACCOUNT_ID}:cluster/${CLUSTER_NAME}"
    }
  ]
}
EOF
)

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "eks-access" \
  --policy-document "$EKS_POLICY"

ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
echo ""
echo "GitHub Actions Role ARN: $ROLE_ARN"
echo ""
echo "Set this as a GitHub secret:"
echo "  gh secret set AWS_ROLE_ARN --body \"$ROLE_ARN\" --repo ${GITHUB_ORG}/${REPO_NAME}"
