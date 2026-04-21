# Requirements Document

## Introduction

A simple web API application designed to be containerized and deployed to Amazon EKS via a GitHub Actions CI/CD pipeline. The pipeline manages both the AWS infrastructure (EKS cluster, ECR registry, IAM roles) and the application itself: on every push to the main branch, the pipeline first reconciles the infrastructure via CloudFormation, then builds, pushes, and deploys the application via Helm. The application intentionally includes fault injection scenarios (togglable via configuration or endpoints) so that developers can practice troubleshooting using the AWS DevOps agent. The system covers the full lifecycle: local development, container build, CI/CD pipeline, infrastructure provisioning, Kubernetes deployment, and observable fault conditions.

## Glossary

- **Application**: The simple HTTP web service (e.g., a REST API) being built and deployed.
- **Container**: A Docker image packaging the Application and its dependencies.
- **EKS_Cluster**: The Amazon Elastic Kubernetes Service cluster where the Application is deployed.
- **GitHub_Actions**: The CI/CD pipeline defined in `.github/workflows/` that provisions infrastructure, builds, tests, and deploys the Application.
- **Infrastructure_Job**: The GitHub_Actions job responsible for creating and updating AWS infrastructure (EKS_Cluster, ECR_Registry, IAM roles) via CloudFormation.
- **Application_Job**: The GitHub_Actions job responsible for building the Container, pushing it to ECR_Registry, and deploying it to the EKS_Cluster via the Helm_Chart.
- **CloudFormation_Stack**: An AWS CloudFormation stack that declaratively manages the lifecycle of the EKS_Cluster, ECR_Registry, and associated IAM roles.
- **Helm_Chart**: The Kubernetes packaging format used to deploy the Application to the EKS_Cluster.
- **Fault_Controller**: The component within the Application responsible for enabling and managing fault injection scenarios.
- **Health_Endpoint**: The HTTP endpoint (`/health`) that reports Application liveness and readiness status.
- **Fault_Scenario**: A named, intentional failure mode that can be activated to simulate real-world issues.
- **ECR_Registry**: The Amazon Elastic Container Registry where Container images are stored.
- **Node_IAM_Role**: The AWS IAM role attached to EKS worker nodes that grants permission to pull images from the ECR_Registry.
- **Deployer_IAM_Role**: The AWS IAM role assumed by GitHub_Actions via OIDC to push images to ECR_Registry, update the CloudFormation_Stack, and deploy to the EKS_Cluster.

---

## Requirements

### Requirement 1: Simple HTTP Web Service

**User Story:** As a developer, I want a simple HTTP web service, so that I have a deployable application to use as the basis for CI/CD and troubleshooting exercises.

#### Acceptance Criteria

1. THE Application SHALL expose an HTTP server on a configurable port (default: 8080).
2. THE Application SHALL expose a root endpoint (`/`) that returns a JSON response containing the application name, version, and current timestamp.
3. THE Application SHALL expose a `/health` endpoint that returns HTTP 200 with `{"status": "healthy"}` when the Application is operating normally.
4. WHEN the Application starts, THE Application SHALL log the configured port and application version to stdout.
5. IF the configured port is already in use, THEN THE Application SHALL exit with a non-zero exit code and log a descriptive error message.

---

### Requirement 2: Containerization

**User Story:** As a developer, I want the application packaged as a Docker container, so that it can be deployed consistently across environments.

#### Acceptance Criteria

1. THE Container SHALL be built from a minimal base image (e.g., `alpine` or `distroless`) to reduce attack surface.
2. THE Container SHALL run the Application as a non-root user.
3. THE Container SHALL expose port 8080.
4. WHEN the Container is started with `docker run`, THE Application SHALL be reachable on the mapped port within 5 seconds.
5. THE Container image SHALL include a `HEALTHCHECK` instruction that calls the `/health` endpoint.

---

### Requirement 3: GitHub Actions CI/CD Pipeline

**User Story:** As a developer, I want a GitHub Actions pipeline composed of an Infrastructure_Job followed by an Application_Job, so that every push to the main branch both reconciles the AWS infrastructure and deploys the latest Application.

#### Acceptance Criteria

1. WHEN a commit is pushed to the `main` branch, THE GitHub_Actions pipeline SHALL execute the Infrastructure_Job before the Application_Job.
2. WHEN the Infrastructure_Job runs, THE Infrastructure_Job SHALL deploy the CloudFormation_Stack to create or update the EKS_Cluster, ECR_Registry, and associated IAM roles.
3. WHEN the Infrastructure_Job fails, THE GitHub_Actions pipeline SHALL stop execution and skip the Application_Job.
4. WHEN the Infrastructure_Job succeeds, THE Application_Job SHALL build the Container image and tag it with the Git commit SHA.
5. WHEN the Container image is built successfully, THE Application_Job SHALL push the tagged image to the ECR_Registry.
6. WHEN the image is pushed to the ECR_Registry, THE Application_Job SHALL deploy the updated image to the EKS_Cluster using the Helm_Chart.
7. IF the Helm deployment fails to reach a ready state within 10 minutes, THEN THE Application_Job SHALL automatically roll back to the previously deployed release and report the failure.
8. IF any pipeline step fails, THEN THE GitHub_Actions pipeline SHALL stop execution and report the failing step without marking the pipeline as successful.
9. THE GitHub_Actions pipeline SHALL authenticate to AWS by assuming the Deployer_IAM_Role via OIDC, without storing long-lived AWS credentials as repository secrets.
10. WHEN a pull request is opened against `main`, THE GitHub_Actions pipeline SHALL run build and test steps only, without executing the Infrastructure_Job or deploying to the EKS_Cluster.

---

### Requirement 4: Kubernetes Deployment via Helm

**User Story:** As a developer, I want the application deployed to EKS using a Helm chart, so that Kubernetes resources are managed consistently and repeatably.

#### Acceptance Criteria

1. THE Helm_Chart SHALL define a Kubernetes `Deployment` with a configurable replica count (default: 2).
2. THE Helm_Chart SHALL define a Kubernetes `Service` of type `ClusterIP` that routes traffic to the Application pods.
3. THE Helm_Chart SHALL configure liveness and readiness probes pointing to the `/health` endpoint.
4. THE Helm_Chart SHALL define resource requests and limits for CPU and memory on the Application container.
5. WHEN the Helm_Chart is deployed, THE EKS_Cluster SHALL pull the Container image from the ECR_Registry using the Node_IAM_Role attached to the EKS_Cluster worker nodes.
6. THE Helm_Chart SHALL support configuring the number of replicas, image tag, and resource limits via `values.yaml` overrides.

---

### Requirement 5: Fault Injection — Memory Leak Simulation

**User Story:** As a developer, I want to simulate a memory leak, so that I can practice identifying and resolving OOMKilled pods in EKS.

#### Acceptance Criteria

1. THE Application SHALL expose a `/fault/memory-leak` endpoint that, when called, causes the Application to continuously allocate memory without releasing it.
2. WHILE the memory leak fault is active, THE Application SHALL continue responding to other HTTP requests until the process is terminated by the OS.
3. WHEN the Application pod is OOMKilled by Kubernetes, THE EKS_Cluster SHALL restart the pod according to the configured restart policy.
4. THE Fault_Controller SHALL log a warning message to stdout when the memory leak fault is activated.

---

### Requirement 6: Fault Injection — CPU Spike Simulation

**User Story:** As a developer, I want to simulate a CPU spike, so that I can practice identifying resource throttling and HPA behavior in EKS.

#### Acceptance Criteria

1. THE Application SHALL expose a `/fault/cpu-spike` endpoint that, when called, starts a CPU-intensive computation loop for a configurable duration (default: 60 seconds).
2. WHILE the CPU spike fault is active, THE Application SHALL remain reachable on the `/health` endpoint.
3. THE Fault_Controller SHALL log the start time and configured duration when the CPU spike fault is activated.

---

### Requirement 7: Fault Injection — Slow Response Simulation

**User Story:** As a developer, I want to simulate slow responses, so that I can practice identifying latency issues and timeout misconfigurations.

#### Acceptance Criteria

1. THE Application SHALL expose a `/fault/slow-response` endpoint that accepts a `delay` query parameter (in milliseconds).
2. WHEN the `/fault/slow-response` endpoint is called with a `delay` value, THE Application SHALL wait for the specified duration before returning an HTTP 200 response.
3. IF the `delay` query parameter is absent or non-numeric, THEN THE Application SHALL return HTTP 400 with a descriptive error message.
4. THE Fault_Controller SHALL log the requested delay value when the slow response fault is activated.

---

### Requirement 8: Fault Injection — Crash Loop Simulation

**User Story:** As a developer, I want to simulate a crash loop, so that I can practice diagnosing CrashLoopBackOff states in EKS.

#### Acceptance Criteria

1. THE Application SHALL expose a `/fault/crash` endpoint that, when called, causes the Application process to exit with a non-zero exit code.
2. WHEN the Application pod exits due to the crash fault, THE EKS_Cluster SHALL restart the pod according to the configured restart policy, producing a CrashLoopBackOff condition after repeated failures.
3. THE Fault_Controller SHALL log a message immediately before the process exits when the crash fault is activated.

---

### Requirement 9: Fault Injection — Dependency Failure Simulation

**User Story:** As a developer, I want to simulate an external dependency failure, so that I can practice diagnosing unhealthy readiness probes and traffic routing issues.

#### Acceptance Criteria

1. THE Application SHALL expose a `/fault/dependency-failure` endpoint that, when called, causes the `/health` endpoint to return HTTP 503 with `{"status": "unhealthy", "reason": "dependency unavailable"}`.
2. WHILE the dependency failure fault is active, THE EKS_Cluster SHALL mark the Application pod as not ready and stop routing traffic to it.
3. THE Application SHALL expose a `/fault/reset` endpoint that deactivates all active faults and restores normal operation.
4. WHEN `/fault/reset` is called, THE Application SHALL return HTTP 200 and THE `/health` endpoint SHALL return HTTP 200 within one request.

---

### Requirement 10: Observability

**User Story:** As a developer, I want structured logs and basic metrics, so that I can use AWS observability tools to diagnose faults.

#### Acceptance Criteria

1. THE Application SHALL emit all log output in structured JSON format to stdout.
2. THE Application SHALL include a `level`, `timestamp`, `message`, and `request_id` field in every log entry.
3. THE Application SHALL expose a `/metrics` endpoint that returns basic runtime metrics (request count, error count, active faults) in a plain-text format compatible with Prometheus scraping.
4. WHEN an HTTP request is received, THE Application SHALL log the HTTP method, path, response status code, and response latency.

---

### Requirement 11: Infrastructure as Code via CloudFormation

**User Story:** As a developer, I want the AWS infrastructure (EKS cluster, ECR registry, IAM roles) defined declaratively in CloudFormation, so that the Infrastructure_Job can create or update the environment idempotently from the pipeline.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL declare the EKS_Cluster, its worker node group, the ECR_Registry, the Node_IAM_Role, and the Deployer_IAM_Role as managed resources.
2. WHEN the CloudFormation_Stack is deployed for the first time, THE Infrastructure_Job SHALL create all declared AWS resources.
3. WHEN the CloudFormation_Stack is deployed and the resources already exist, THE Infrastructure_Job SHALL update only the resources whose configuration has changed.
4. IF a CloudFormation_Stack update fails, THEN THE CloudFormation_Stack SHALL automatically roll back to its previous successful state.
5. THE CloudFormation_Stack SHALL output the ECR_Registry URI, the EKS_Cluster name, and the Deployer_IAM_Role ARN for consumption by the Application_Job.
6. THE CloudFormation_Stack SHALL configure the EKS_Cluster OIDC provider to allow the Deployer_IAM_Role to be assumed by the GitHub_Actions pipeline.
