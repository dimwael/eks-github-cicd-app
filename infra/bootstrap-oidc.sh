#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# bootstrap-oidc.sh — one-time operator bootstrap for eks-github-cicd-app
# =============================================================================
#
# Run this script ONCE, locally, with admin AWS credentials BEFORE the first
# pipeline run. It creates the two things that must exist before GitHub Actions
# can assume any role in this account:
#
#   1. The IAM OIDC identity provider for token.actions.githubusercontent.com
#   2. A minimal bootstrap Deployer IAM role scoped to this repo, with just
#      enough permissions to deploy infra/cloudformation/eks-cicd-stack.yaml
#      for the FIRST time. Once the stack exists, it manages the long-term
#      Deployer_IAM_Role itself.
#
# Operator runbook (4 steps):
#
#   Step 1. Run this script with admin AWS credentials:
#             ./infra/bootstrap-oidc.sh
#
#   Step 2. Copy the printed role ARN into GitHub repo secrets:
#             gh secret set AWS_ROLE_ARN --body "<arn>" \
#               --repo dimwael/eks-github-cicd-app
#
#   Step 3. Set the repo variables that the CFN template needs for the VPC
#           it will deploy the EKS cluster into:
#             gh variable set AWS_OIDC_PROVIDER_ARN --body "<arn>" \
#               --repo dimwael/eks-github-cicd-app
#             gh variable set VPC_ID --body "vpc-xxxxxxxx" \
#               --repo dimwael/eks-github-cicd-app
#             gh variable set SUBNET_IDS --body "subnet-aaaa,subnet-bbbb" \
#               --repo dimwael/eks-github-cicd-app
#
#   Step 4. Push to main. Infrastructure_Job will deploy the CFN stack;
#           Application_Job will build, push, and helm upgrade the app.
#
# This script is idempotent and safe to re-run.
# =============================================================================

REGION="${REGION:-us-east-1}"
GITHUB_ORG="${GITHUB_ORG:-dimwael}"
REPO_NAME="${REPO_NAME:-eks-github-cicd-app}"
ROLE_NAME="${ROLE_NAME:-eks-github-cicd-app-bootstrap-deployer}"
STACK_NAME="${STACK_NAME:-eks-github-cicd-app-stack}"
CLUSTER_NAME="${CLUSTER_NAME:-eks-github-cicd-app}"

# Resolve the account ID from the caller identity if the operator didn't set it
# explicitly. This keeps the script portable across AWS accounts.
ACCOUNT_ID="${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"

OIDC_URL="token.actions.githubusercontent.com"
OIDC_PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${OIDC_URL}"

echo "Account:          ${ACCOUNT_ID}"
echo "Region:           ${REGION}"
echo "GitHub repo:      ${GITHUB_ORG}/${REPO_NAME}"
echo "Bootstrap role:   ${ROLE_NAME}"
echo "CFN stack name:   ${STACK_NAME}"
echo ""

# -----------------------------------------------------------------------------
# 1. IAM OIDC identity provider for GitHub Actions (idempotent)
# -----------------------------------------------------------------------------
echo "==> Ensuring GitHub Actions OIDC provider exists..."
if aws iam list-open-id-connect-providers \
     --query "OpenIDConnectProviderList[?Arn=='${OIDC_PROVIDER_ARN}'] | [0].Arn" \
     --output text 2>/dev/null | grep -q "${OIDC_PROVIDER_ARN}"; then
  echo "    OIDC provider already exists: ${OIDC_PROVIDER_ARN}"
else
  aws iam create-open-id-connect-provider \
    --url "https://${OIDC_URL}" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" \
    >/dev/null
  echo "    Created OIDC provider: ${OIDC_PROVIDER_ARN}"
fi

# -----------------------------------------------------------------------------
# 2. Bootstrap Deployer role (create or update trust policy)
# -----------------------------------------------------------------------------
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
          "${OIDC_URL}:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "${OIDC_URL}:sub": "repo:${GITHUB_ORG}/${REPO_NAME}:*"
        }
      }
    }
  ]
}
EOF
)

echo "==> Ensuring bootstrap Deployer role ${ROLE_NAME}..."
if aws iam get-role --role-name "${ROLE_NAME}" >/dev/null 2>&1; then
  echo "    Role exists; updating trust policy..."
  aws iam update-assume-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-document "${TRUST_POLICY}"
else
  echo "    Creating role..."
  aws iam create-role \
    --role-name "${ROLE_NAME}" \
    --description "Bootstrap Deployer role for ${GITHUB_ORG}/${REPO_NAME} GitHub Actions first-run CFN deploy" \
    --assume-role-policy-document "${TRUST_POLICY}" \
    >/dev/null
fi

# -----------------------------------------------------------------------------
# 3. Inline policy: minimum permissions to deploy the CFN stack the FIRST time.
#    After the stack exists, the stack-managed Deployer_IAM_Role supersedes
#    this role for steady-state deploys.
# -----------------------------------------------------------------------------
INLINE_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormationStackManage",
      "Effect": "Allow",
      "Action": "cloudformation:*",
      "Resource": [
        "arn:aws:cloudformation:${REGION}:${ACCOUNT_ID}:stack/${STACK_NAME}/*",
        "arn:aws:cloudformation:${REGION}:${ACCOUNT_ID}:stack/${STACK_NAME}/*/*"
      ]
    },
    {
      "Sid": "CloudFormationServiceLevel",
      "Effect": "Allow",
      "Action": [
        "cloudformation:DescribeStacks",
        "cloudformation:ValidateTemplate",
        "cloudformation:GetTemplateSummary",
        "cloudformation:ListStacks",
        "cloudformation:CreateChangeSet",
        "cloudformation:DescribeChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IamRoleManageScoped",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::${ACCOUNT_ID}:role/${CLUSTER_NAME}-*"
    },
    {
      "Sid": "EksServiceLinkedRoleRead",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:ListAttachedRolePolicies"
      ],
      "Resource": [
        "arn:aws:iam::${ACCOUNT_ID}:role/aws-service-role/eks.amazonaws.com/AWSServiceRoleForAmazonEKS",
        "arn:aws:iam::${ACCOUNT_ID}:role/aws-service-role/eks-nodegroup.amazonaws.com/AWSServiceRoleForAmazonEKSNodegroup",
        "arn:aws:iam::${ACCOUNT_ID}:role/aws-service-role/eks-fargate.amazonaws.com/AWSServiceRoleForAmazonEKSForFargate"
      ]
    },
    {
      "Sid": "EksServiceLinkedRoleCreate",
      "Effect": "Allow",
      "Action": "iam:CreateServiceLinkedRole",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "iam:AWSServiceName": [
            "eks.amazonaws.com",
            "eks-nodegroup.amazonaws.com",
            "eks-fargate.amazonaws.com"
          ]
        }
      }
    },
    {
      "Sid": "Ec2Describe",
      "Effect": "Allow",
      "Action": "ec2:Describe*",
      "Resource": "*"
    },
    {
      "Sid": "EksClusterAndNodegroup",
      "Effect": "Allow",
      "Action": "eks:*",
      "Resource": [
        "arn:aws:eks:${REGION}:${ACCOUNT_ID}:cluster/${CLUSTER_NAME}",
        "arn:aws:eks:${REGION}:${ACCOUNT_ID}:nodegroup/${CLUSTER_NAME}/*/*"
      ]
    },
    {
      "Sid": "EksServiceLevel",
      "Effect": "Allow",
      "Action": [
        "eks:CreateCluster",
        "eks:DescribeCluster",
        "eks:ListClusters",
        "eks:TagResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EcrRepoManage",
      "Effect": "Allow",
      "Action": "ecr:*",
      "Resource": "arn:aws:ecr:${REGION}:${ACCOUNT_ID}:repository/${CLUSTER_NAME}"
    },
    {
      "Sid": "EcrServiceLevel",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:CreateRepository",
        "ecr:DescribeRepositories"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)

echo "==> Attaching inline bootstrap policy..."
aws iam put-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-name "bootstrap-cfn-deploy" \
  --policy-document "${INLINE_POLICY}"

# -----------------------------------------------------------------------------
# 4. Summary — everything the operator needs for steps 2 and 3 of the runbook
# -----------------------------------------------------------------------------
ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query 'Role.Arn' --output text)

echo ""
echo "============================================================"
echo "Bootstrap complete."
echo "============================================================"
echo ""
echo "  Bootstrap Deployer role ARN:"
echo "    ${ROLE_ARN}"
echo ""
echo "  GitHub Actions OIDC provider ARN:"
echo "    ${OIDC_PROVIDER_ARN}"
echo ""
echo "Next steps — copy/paste these commands:"
echo ""
echo "  # Set the role ARN as a GitHub repo secret (used by cd.yml)"
echo "  gh secret set AWS_ROLE_ARN --body \"${ROLE_ARN}\" --repo ${GITHUB_ORG}/${REPO_NAME}"
echo ""
echo "  # Set the OIDC provider ARN as a GitHub repo variable"
echo "  # (passed to the CFN template as GitHubOIDCProviderArn)"
echo "  gh variable set AWS_OIDC_PROVIDER_ARN --body \"${OIDC_PROVIDER_ARN}\" --repo ${GITHUB_ORG}/${REPO_NAME}"
echo ""
echo "  # Also set the target VPC and subnets as GitHub repo variables"
echo "  # (at least two subnets spanning different AZs):"
echo "  gh variable set VPC_ID     --body \"vpc-xxxxxxxx\"             --repo ${GITHUB_ORG}/${REPO_NAME}"
echo "  gh variable set SUBNET_IDS --body \"subnet-aaaa,subnet-bbbb\" --repo ${GITHUB_ORG}/${REPO_NAME}"
echo ""
echo "Then push to main — the pipeline will take it from there."
