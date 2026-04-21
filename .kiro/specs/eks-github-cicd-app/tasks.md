# Implementation Plan: eks-github-cicd-app

## Overview

Incremental implementation of a Python FastAPI application deployed to Amazon EKS via a two-job GitHub Actions CI/CD pipeline. The `Infrastructure_Job` deploys a single CloudFormation stack (`infra/cloudformation/eks-cicd-stack.yaml`) that declares the EKS cluster, ECR registry, and IAM roles; the `Application_Job` builds/pushes the container and runs `helm upgrade --install --atomic`. The application and Helm chart already exist — the remaining work is IaC, pipeline wiring, and cleanup of legacy bash scripts.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Directory layout `app/`, `tests/`, `helm/eks-github-cicd-app/templates/` in place
  - `requirements.txt` pins `fastapi`, `uvicorn[standard]`, `httpx`, `anyio`, `pytest`, `pytest-anyio`, `hypothesis`, `pydantic-settings`
  - `app/config.py` reads `PORT`, `APP_VERSION`, `CPU_SPIKE_DURATION` via `pydantic-settings`
  - _Requirements: 1.1, 1.4_

- [x] 2. Implement structured JSON logger
  - [x] 2.1 `app/logger.py` with `JSONFormatter`, `request_id_var` ContextVar, `get_logger()` helper
    - _Requirements: 10.1, 10.2_

  - [x]* 2.2 Unit tests for logger output shape in `tests/test_logger.py`
    - _Requirements: 10.1, 10.2_

  - [x]* 2.3 Property test for log entry fields
    - `# Feature: eks-github-cicd-app, Property 10: All log entries are valid structured JSON with required fields`
    - _Requirements: 10.1, 10.2, 10.4_

- [x] 3. Implement FaultController
  - [x] 3.1 `app/fault.py` — `FaultController` with memory-leak, cpu-spike, slow-response, dependency-failure, reset, and query methods
    - _Requirements: 5.1, 5.4, 6.1, 6.3, 7.1, 7.4, 8.3, 9.3_

  - [x]* 3.2 Unit tests for state transitions in `tests/test_fault.py`
    - _Requirements: 5.1, 6.1, 7.1, 9.3_

  - [x]* 3.3 Property test for fault activation liveness
    - `# Feature: eks-github-cicd-app, Property 4: Fault activation does not break server liveness`
    - _Requirements: 5.2, 6.2_

  - [x]* 3.4 Property test for fault activation warning logs
    - `# Feature: eks-github-cicd-app, Property 5: Fault activation produces a structured log warning`
    - _Requirements: 5.4, 6.3, 7.4, 8.3_

  - [x]* 3.5 Property test for reset restores health
    - `# Feature: eks-github-cicd-app, Property 9: Reset restores healthy state`
    - _Requirements: 9.3, 9.4_

- [x] 4. Implement Metrics
  - [x] 4.1 `app/metrics.py` with thread-safe counters and `prometheus_text()` serializer
    - _Requirements: 10.3_

  - [x]* 4.2 Unit tests for metrics format in `tests/test_metrics.py`
    - _Requirements: 10.3_

  - [x]* 4.3 Property test for metrics endpoint
    - `# Feature: eks-github-cicd-app, Property 11: Metrics endpoint contains required metric names`
    - _Requirements: 10.3_

- [x] 5. Implement request logging middleware
  - `app/middleware.py` — `RequestLoggingMiddleware` sets `request_id_var`, logs method/path/status/latency_ms, increments metrics
  - _Requirements: 10.4_

- [x] 6. Implement FastAPI route handlers and wire application
  - [x] 6.1 `app/main.py` — all routes (`/`, `/health`, `/metrics`, `/fault/*`) wired
    - _Requirements: 1.2, 1.3, 5.1, 6.1, 7.1, 7.3, 8.1, 9.1, 9.3, 10.3_

  - [x] 6.2 Uvicorn startup entrypoint with `EADDRINUSE` handling
    - _Requirements: 1.1, 1.4, 1.5_

  - [x]* 6.3 Unit tests for route handlers in `tests/test_handlers.py`
    - _Requirements: 1.2, 1.3, 7.3, 9.1, 9.4_

  - [x]* 6.4 Property test for root endpoint response shape
    - `# Feature: eks-github-cicd-app, Property 1: Root endpoint response shape`
    - _Requirements: 1.2_

  - [x]* 6.5 Property test for slow response delay
    - `# Feature: eks-github-cicd-app, Property 6: Slow response respects delay parameter`
    - _Requirements: 7.1, 7.2_

  - [x]* 6.6 Property test for invalid delay returns 400
    - `# Feature: eks-github-cicd-app, Property 7: Invalid delay parameter returns HTTP 400`
    - _Requirements: 7.3_

  - [x]* 6.7 Property test for dependency failure health
    - `# Feature: eks-github-cicd-app, Property 8: Dependency failure changes health status`
    - _Requirements: 9.1_

- [x] 7. Checkpoint — application unit and property tests pass
  - `pytest tests/ -v` runs clean against existing code
  - Ask the user if any questions arise before proceeding.

- [x] 8. Create Dockerfile
  - `python:3.12-slim` base, `ARG APP_VERSION`, non-root `appuser`, `HEALTHCHECK` hitting `/health`, `CMD` runs uvicorn on port 8080
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 9. Create Helm chart
  - [x] 9.1 `helm/eks-github-cicd-app/Chart.yaml` — apiVersion v2, name, version 0.1.0
    - _Requirements: 4.1_

  - [x] 9.2 `helm/eks-github-cicd-app/templates/deployment.yaml`, `service.yaml`, `serviceaccount.yaml`, `_helpers.tpl`
    - Deployment with replica count, liveness/readiness probes on `/health`, resources, `APP_VERSION` env from image tag
    - Service type ClusterIP on port 8080
    - ServiceAccount created by default
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 9.3 Update `helm/eks-github-cicd-app/values.yaml` for Node_IAM_Role-based ECR pulls
    - Confirm `serviceAccount.annotations: {}` default (no IRSA annotation required — ECR pulls happen via Node_IAM_Role at the kubelet level, not via pod identity)
    - Add a short comment in `values.yaml` documenting that `serviceAccount.annotations` is retained only for future AWS API access from pods
    - Do not add `eks.amazonaws.com/role-arn` as a required value
    - _Requirements: 4.5, 4.6_

  - [ ]* 9.4 Property test for Helm values reflection
    - `# Feature: eks-github-cicd-app, Property 12: Helm chart values are reflected in rendered output`
    - Use `@given(st.integers(min_value=1, max_value=10), st.text(min_size=1))` for `replicaCount` and `image.tag`
    - Run `helm template` via `subprocess` with `--set` overrides and assert rendered YAML contains expected values via `yaml.safe_load`
    - _Requirements: 4.1, 4.4, 4.6_

- [ ] 10. Create CloudFormation infrastructure template
  - [x] 10.1 Create `infra/cloudformation/eks-cicd-stack.yaml`
    - **Parameters**: `ClusterName` (default `eks-github-cicd-app`), `KubernetesVersion` (default `1.30`), `NodeInstanceType` (default `t3.medium`), `GitHubOrg` (default `dimwael`), `GitHubRepo` (default `eks-github-cicd-app`), `VpcId` (AWS::EC2::VPC::Id), `SubnetIds` (List<AWS::EC2::Subnet::Id>)
    - _Requirements: 11.1, 11.2_

  - [x] 10.2 Declare IAM roles in the template
    - `EksClusterRole` — trust `eks.amazonaws.com`, managed policy `AmazonEKSClusterPolicy`
    - `NodeInstanceRole` (Node_IAM_Role) — trust `ec2.amazonaws.com`, managed policies: `AmazonEKSWorkerNodePolicy`, `AmazonEC2ContainerRegistryReadOnly`, `AmazonEKS_CNI_Policy`
    - `DeployerRole` (Deployer_IAM_Role) — trust the GitHub OIDC provider ARN with condition `token.actions.githubusercontent.com:sub` matching `repo:dimwael/eks-github-cicd-app:*` and `aud = sts.amazonaws.com`; inline policies granting `cloudformation:*` on `arn:aws:cloudformation:*:*:stack/eks-github-cicd-app-stack/*`, `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:DescribeRepositories`, `eks:DescribeCluster` on the cluster, and `iam:PassRole` for `EksClusterRole` and `NodeInstanceRole`
    - _Requirements: 11.1, 11.6, 3.9_

  - [x] 10.3 Declare EKS cluster and node group in the template
    - `EksCluster` (`AWS::EKS::Cluster`) — version from `KubernetesVersion` param, `RoleArn: !GetAtt EksClusterRole.Arn`, `ResourcesVpcConfig` using `SubnetIds` parameter
    - `EksNodeGroup` (`AWS::EKS::Nodegroup`) — `ClusterName: !Ref EksCluster`, `NodeRole: !GetAtt NodeInstanceRole.Arn`, `InstanceTypes: [!Ref NodeInstanceType]`, `ScalingConfig: { MinSize: 1, DesiredSize: 2, MaxSize: 4 }`, `Subnets: !Ref SubnetIds`
    - _Requirements: 11.1, 4.5_

  - [x] 10.4 Declare ECR repository in the template
    - `EcrRepository` (`AWS::ECR::Repository`) — `RepositoryName: eks-github-cicd-app`, `ImageScanningConfiguration: { ScanOnPush: true }`, `EncryptionConfiguration: { EncryptionType: AES256 }`
    - _Requirements: 11.1, 3.2_

  - [x] 10.5 Declare stack outputs
    - `EcrRepositoryUri` → `!GetAtt EcrRepository.RepositoryUri`, exported as `${AWS::StackName}-EcrRepositoryUri`
    - `EksClusterName` → `!Ref EksCluster`, exported as `${AWS::StackName}-EksClusterName`
    - `DeployerRoleArn` → `!GetAtt DeployerRole.Arn`, exported as `${AWS::StackName}-DeployerRoleArn`
    - _Requirements: 11.5_

  - [x] 10.6 Lint the template
    - Run `cfn-lint infra/cloudformation/eks-cicd-stack.yaml` locally and fix any errors/warnings
    - _Requirements: 11.1_

- [ ] 11. Create bootstrap script for the GitHub OIDC provider and initial Deployer_IAM_Role
  - [x] 11.1 Create `infra/bootstrap-oidc.sh`
    - `set -euo pipefail`; vars for `ACCOUNT_ID`, `REGION`, `GITHUB_ORG=dimwael`, `REPO_NAME=eks-github-cicd-app`, `ROLE_NAME=eks-github-cicd-app-bootstrap-deployer`, `STACK_NAME=eks-github-cicd-app-stack`
    - Idempotently create the IAM OIDC provider for `token.actions.githubusercontent.com` (skip if exists)
    - Create or update a minimal bootstrap Deployer role with trust policy scoped to `repo:dimwael/eks-github-cicd-app:*`
    - Attach a single inline policy granting the minimum permissions to deploy the CFN stack the first time: `cloudformation:*` on `arn:aws:cloudformation:${REGION}:${ACCOUNT_ID}:stack/${STACK_NAME}/*`, `iam:CreateRole`, `iam:DeleteRole`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `iam:PutRolePolicy`, `iam:DeleteRolePolicy`, `iam:GetRole`, `iam:PassRole`, `iam:TagRole`, `ec2:Describe*`, `eks:*`, `ecr:*`
    - Print the role ARN and a ready-to-copy `gh secret set AWS_ROLE_ARN --body "<arn>" --repo dimwael/eks-github-cicd-app` command
    - `chmod +x infra/bootstrap-oidc.sh`
    - _Requirements: 3.9, 11.6_

- [ ] 12. Remove obsolete bash infrastructure scripts
  - [x] 12.1 Delete legacy scripts replaced by the CFN template + bootstrap script
    - Delete `infra/01-create-ecr.sh` (ECR is now in the CFN stack)
    - Delete `infra/02-create-eks-cluster.sh` (EKS cluster and node group are now in the CFN stack)
    - Delete `infra/03-create-irsa-role.sh` (ECR pulls use Node_IAM_Role, not IRSA)
    - Delete `infra/04-create-github-oidc-role.sh` (replaced by `infra/bootstrap-oidc.sh` + CFN-managed Deployer_IAM_Role)
    - _Requirements: 11.1_

- [ ] 13. Create GitHub Actions CI workflow (PR check)
  - [x] 13.1 Create `.github/workflows/ci.yml`
    - Trigger: `pull_request` targeting `main`
    - Job `test`: `actions/checkout@v4`, `actions/setup-python@v5` (python 3.12), `pip install -r requirements.txt`, `pytest tests/ -v`
    - Also run `cfn-lint infra/cloudformation/eks-cicd-stack.yaml` and `helm lint helm/eks-github-cicd-app/`
    - No AWS credentials, no Docker build, no deploy
    - _Requirements: 3.10_

- [ ] 14. Create GitHub Actions CD workflow (two-job pipeline)
  - [x] 14.1 Create `.github/workflows/cd.yml` with top-level config
    - Trigger: `push` to `main`
    - Top-level `permissions: { id-token: write, contents: read }`
    - Top-level `env: { AWS_REGION: us-east-1, STACK_NAME: eks-github-cicd-app-stack, CLUSTER_NAME: eks-github-cicd-app }`
    - _Requirements: 3.1, 3.9_

  - [x] 14.2 Define `infrastructure` job
    - `runs-on: ubuntu-latest`
    - `outputs`: `ecr_uri`, `cluster_name` derived from CFN stack outputs
    - Steps:
      1. `actions/checkout@v4`
      2. `aws-actions/configure-aws-credentials@v4` with `role-to-assume: ${{ secrets.AWS_ROLE_ARN }}`, `aws-region: ${{ env.AWS_REGION }}`
      3. `aws cloudformation deploy --template-file infra/cloudformation/eks-cicd-stack.yaml --stack-name $STACK_NAME --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset --parameter-overrides VpcId=${{ vars.VPC_ID }} SubnetIds=${{ vars.SUBNET_IDS }}`
      4. Read outputs with `aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs'` and write `ecr_uri` and `cluster_name` to `$GITHUB_OUTPUT`
    - _Requirements: 3.2, 3.3, 11.2, 11.3, 11.4, 11.5_

  - [x] 14.3 Define `application` job
    - `needs: infrastructure`
    - `runs-on: ubuntu-latest`
    - `env`: consume `ECR_URI: ${{ needs.infrastructure.outputs.ecr_uri }}`, `CLUSTER_NAME: ${{ needs.infrastructure.outputs.cluster_name }}`
    - Steps:
      1. `actions/checkout@v4`
      2. `aws-actions/configure-aws-credentials@v4` (same OIDC role)
      3. `aws-actions/amazon-ecr-login@v2`
      4. `docker build --build-arg APP_VERSION=${{ github.sha }} -t $ECR_URI:${{ github.sha }} .`
      5. `docker push $ECR_URI:${{ github.sha }}`
      6. `aws eks update-kubeconfig --name $CLUSTER_NAME --region $AWS_REGION`
      7. `helm upgrade --install eks-github-cicd-app ./helm/eks-github-cicd-app --atomic --timeout 10m --set image.repository=$ECR_URI --set image.tag=${{ github.sha }}`
    - _Requirements: 3.4, 3.5, 3.6, 3.7, 3.8_

- [ ] 15. Final checkpoint — verify artifacts and document operator runbook
  - [x] 15.1 Verify full test suite passes locally
    - `pytest tests/ -v` — all unit and property tests green
    - `cfn-lint infra/cloudformation/eks-cicd-stack.yaml` — no errors
    - `helm lint helm/eks-github-cicd-app/` — no errors
    - Ensure all tests pass, ask the user if questions arise.

  - [x] 15.2 Document the one-time operator runbook inside `infra/bootstrap-oidc.sh` header comment
    - Step 1: operator runs `infra/bootstrap-oidc.sh` locally with admin credentials
    - Step 2: operator copies the printed `AWS_ROLE_ARN` into GitHub repo secrets
    - Step 3: operator sets repo variables `VPC_ID` and `SUBNET_IDS` (comma-separated) for the target VPC
    - Step 4: operator pushes to `main` — Infrastructure_Job deploys the CFN stack, Application_Job builds/pushes/deploys
    - Expected end-to-end success: CFN stack status `CREATE_COMPLETE` or `UPDATE_COMPLETE`, Helm release `deployed`, `kubectl get pods` shows 2 Ready pods, `kubectl port-forward svc/eks-github-cicd-app 8080:8080 && curl /health` returns `{"status":"healthy"}`

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Tasks already completed (marked `[x]`) reflect existing code in the repo; only the Helm `values.yaml` needs a small doc tweak (9.3)
- Property tests use Hypothesis with `@settings(max_examples=100)`
- AWS Account: `649976227195`, Region: `us-east-1`, GitHub user: `dimwael`
- The CloudFormation stack is the single source of truth for EKS, ECR, Node_IAM_Role, and the steady-state Deployer_IAM_Role; the bootstrap script only exists to create the OIDC provider and the *initial* minimal Deployer role needed for the very first pipeline run
- Image pulls use the Node_IAM_Role (managed policy `AmazonEC2ContainerRegistryReadOnly`) at the kubelet level — no IRSA required for the app ServiceAccount
