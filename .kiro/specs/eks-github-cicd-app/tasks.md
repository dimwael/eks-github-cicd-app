# Implementation Plan: eks-github-cicd-app

## Overview

Incremental implementation of a Python FastAPI application deployed to Amazon EKS via GitHub Actions CI/CD, with fault injection endpoints for DevOps troubleshooting practice. Tasks build from core application code through containerization, Helm packaging, AWS infrastructure, and CI/CD pipeline wiring.

## Tasks

- [ ] 1. Set up project structure and dependencies
  - Create the directory layout: `app/`, `tests/`, `helm/eks-github-cicd-app/templates/`, `.github/workflows/`
  - Create `requirements.txt` with pinned versions: `fastapi`, `uvicorn[standard]`, `httpx`, `anyio`, `pytest`, `pytest-anyio`, `hypothesis`, `pydantic-settings`
  - Create `app/__init__.py`, `tests/__init__.py` (empty)
  - Create `app/config.py` using `pydantic-settings` `BaseSettings` to read `PORT` (default `8080`), `APP_VERSION` (default `dev`), `CPU_SPIKE_DURATION` (default `60`) from environment
  - _Requirements: 1.1, 1.4_

- [ ] 2. Implement structured JSON logger
  - [ ] 2.1 Create `app/logger.py`
    - Subclass `logging.Formatter` to serialize each `LogRecord` to a single-line JSON string with fields `level`, `timestamp` (ISO-8601 UTC), `message`
    - Use `contextvars.ContextVar` named `request_id_var` to carry per-request ID; include it in every log record when set
    - Configure the root logger with this formatter writing to `sys.stdout`
    - Expose a `get_logger(name: str) -> logging.Logger` helper
    - _Requirements: 10.1, 10.2_

  - [ ]* 2.2 Write unit tests for logger output shape
    - In `tests/test_logger.py`, use `capsys` to capture stdout and assert each emitted line is valid JSON with `level`, `timestamp`, `message` keys
    - _Requirements: 10.1, 10.2_

  - [ ]* 2.3 Write property test for log entry fields (Property 10)
    - `# Feature: eks-github-cicd-app, Property 10: All log entries are valid structured JSON with required fields`
    - In `tests/test_properties.py`, use `@given(st.sampled_from(["GET", "POST"]), st.text(min_size=1, alphabet=...))` to verify every request log line contains `level`, `timestamp`, `message`, `request_id`, `method`, `path`, `status`, `latency_ms`
    - _Requirements: 10.1, 10.2, 10.4_

- [ ] 3. Implement FaultController
  - [ ] 3.1 Create `app/fault.py` with `FaultController` class
    - Internal state: `_dependency_failure: bool`, `_slow_delay_ms: int`, `_stop_event: threading.Event`, `_lock: threading.Lock`
    - `activate_memory_leak()`: log WARNING, start background `threading.Thread` that appends 10 MB `bytearray` chunks to a module-level list each second until `_stop_event` is set
    - `activate_cpu_spike(duration_sec: int)`: log WARNING with start time and duration, submit a tight arithmetic loop to `concurrent.futures.ThreadPoolExecutor(max_workers=1)` that runs until `_stop_event` is set or duration expires
    - `activate_slow_response(delay_ms: int)`: log WARNING with delay value, set `_slow_delay_ms`
    - `activate_dependency_failure()`: log WARNING, set `_dependency_failure = True`
    - `reset()`: set `_stop_event`, clear all state flags, create a new `_stop_event` for future faults, log INFO
    - `is_healthy() -> bool`: return `not self._dependency_failure`
    - `slow_delay_ms() -> int`: return current delay (0 if not active)
    - `active_faults() -> list[str]`: return list of currently active fault names
    - _Requirements: 5.1, 5.4, 6.1, 6.3, 7.1, 7.4, 8.3, 9.3_

  - [ ]* 3.2 Write unit tests for FaultController state transitions
    - In `tests/test_fault.py`, test: `is_healthy()` is `True` initially; `False` after `activate_dependency_failure()`; `True` after `reset()`; `active_faults()` returns correct names; `slow_delay_ms()` returns 0 after reset
    - _Requirements: 5.1, 6.1, 7.1, 9.3_

  - [ ]* 3.3 Write property test for fault activation liveness (Property 4)
    - `# Feature: eks-github-cicd-app, Property 4: Fault activation does not break server liveness`
    - Use `@given(st.sampled_from(["memory-leak", "cpu-spike", "slow-response"]))` to activate each fault and assert `/health` still returns HTTP 200
    - _Requirements: 5.2, 6.2_

  - [ ]* 3.4 Write property test for fault activation warning logs (Property 5)
    - `# Feature: eks-github-cicd-app, Property 5: Fault activation produces a structured log warning`
    - Use `@given(st.sampled_from(["memory-leak", "cpu-spike", "slow-response", "dependency-failure"]))` to verify at least one WARNING-level JSON log line is emitted containing the fault name
    - _Requirements: 5.4, 6.3, 7.4, 8.3_

  - [ ]* 3.5 Write property test for reset restores health (Property 9)
    - `# Feature: eks-github-cicd-app, Property 9: Reset restores healthy state`
    - Use `@given(st.lists(st.sampled_from(["memory-leak", "cpu-spike", "slow-response", "dependency-failure"])))` to activate arbitrary fault combinations, call reset, then assert `/health` returns HTTP 200 with `{"status": "healthy"}`
    - _Requirements: 9.3, 9.4_

- [ ] 4. Implement Metrics
  - [ ] 4.1 Create `app/metrics.py` with `Metrics` class
    - Thread-safe counters `_request_count` and `_error_count` protected by `threading.Lock`
    - `increment_requests()`, `increment_errors()` methods
    - `prometheus_text(active_faults: list[str]) -> str`: serialize to Prometheus text format with `http_requests_total`, `http_errors_total`, `active_faults` gauge
    - Module-level singleton `metrics = Metrics()`
    - _Requirements: 10.3_

  - [ ]* 4.2 Write unit tests for metrics format
    - In `tests/test_metrics.py`, verify counter increments and that `prometheus_text()` output contains the three required metric names with correct `# HELP` and `# TYPE` lines
    - _Requirements: 10.3_

  - [ ]* 4.3 Write property test for metrics endpoint (Property 11)
    - `# Feature: eks-github-cicd-app, Property 11: Metrics endpoint contains required metric names`
    - Use `@given(st.integers(min_value=1, max_value=1000))` to simulate N requests and assert `/metrics` response body contains `http_requests_total`, `http_errors_total`, `active_faults`
    - _Requirements: 10.3_

- [ ] 5. Implement request logging middleware
  - Create `app/middleware.py` with a Starlette `BaseHTTPMiddleware` subclass `RequestLoggingMiddleware`
  - On each request: generate a UUID4 `request_id`, set `request_id_var` context var, record start time
  - After response: compute `latency_ms`, log JSON with `method`, `path`, `status`, `latency_ms`, `request_id`; call `metrics.increment_requests()`; call `metrics.increment_errors()` if status >= 500
  - _Requirements: 10.4_

- [ ] 6. Implement FastAPI route handlers and wire application
  - [ ] 6.1 Create `app/main.py`
    - Instantiate `FastAPI()`, add `RequestLoggingMiddleware`, register all routes listed in the design
    - `GET /`: return `{"app": "eks-github-cicd-app", "version": settings.app_version, "timestamp": utcnow().isoformat()}`
    - `GET /health`: return `{"status": "healthy"}` (HTTP 200) or `{"status": "unhealthy", "reason": "dependency unavailable"}` (HTTP 503) based on `fault_controller.is_healthy()`
    - `GET /metrics`: return `fault_controller.active_faults()` passed to `metrics.prometheus_text()` as `text/plain`
    - `POST /fault/memory-leak`: call `fault_controller.activate_memory_leak()`, return HTTP 200
    - `POST /fault/cpu-spike`: call `fault_controller.activate_cpu_spike(settings.cpu_spike_duration)`, return HTTP 200
    - `GET /fault/slow-response`: validate `delay` query param (absent or non-integer → HTTP 400 JSON error); call `fault_controller.activate_slow_response(delay_ms)`; `await asyncio.sleep(delay_ms / 1000)`; return HTTP 200
    - `POST /fault/crash`: log WARNING, call `os._exit(1)`
    - `POST /fault/dependency-failure`: call `fault_controller.activate_dependency_failure()`, return HTTP 200
    - `POST /fault/reset`: call `fault_controller.reset()`, return HTTP 200
    - Module-level singletons: `settings = Settings()`, `fault_controller = FaultController()`, `app = FastAPI()`
    - _Requirements: 1.2, 1.3, 5.1, 6.1, 7.1, 7.3, 8.1, 9.1, 9.3, 10.3_

  - [ ] 6.2 Add Uvicorn startup entrypoint
    - At the bottom of `app/main.py`, add `if __name__ == "__main__":` block that catches `OSError` with `errno.EADDRINUSE` on `uvicorn.run()`, logs a structured error, and calls `sys.exit(1)`
    - Log configured port and version to stdout before starting Uvicorn
    - _Requirements: 1.1, 1.4, 1.5_

  - [ ]* 6.3 Write unit tests for route handlers
    - In `tests/test_handlers.py`, use `httpx.AsyncClient(app=app, base_url="http://test")` with `@pytest.mark.anyio`
    - Cover: `GET /` returns 200 with `app`, `version`, `timestamp`; `GET /health` returns 200 normally; `GET /health` returns 503 after dependency-failure; `GET /health` returns 200 after reset; `GET /fault/slow-response` without delay returns 400; `POST /fault/reset` returns 200
    - _Requirements: 1.2, 1.3, 7.3, 9.1, 9.4_

  - [ ]* 6.4 Write property test for root endpoint response shape (Property 1)
    - `# Feature: eks-github-cicd-app, Property 1: Root endpoint response shape`
    - Use `@given(st.text(min_size=1))` for version strings; assert `GET /` always returns HTTP 200 with non-empty `app`, `version`, `timestamp` fields
    - _Requirements: 1.2_

  - [ ]* 6.5 Write property test for slow response delay (Property 6)
    - `# Feature: eks-github-cicd-app, Property 6: Slow response respects delay parameter`
    - Use `@given(st.integers(min_value=0, max_value=200))` to assert response time >= delay_ms and status is 200
    - _Requirements: 7.1, 7.2_

  - [ ]* 6.6 Write property test for invalid delay returns 400 (Property 7)
    - `# Feature: eks-github-cicd-app, Property 7: Invalid delay parameter returns HTTP 400`
    - Use `@given(st.text().filter(lambda s: not s.lstrip('-').isdigit()))` to assert HTTP 400 with JSON `error` field
    - _Requirements: 7.3_

  - [ ]* 6.7 Write property test for dependency failure health (Property 8)
    - `# Feature: eks-github-cicd-app, Property 8: Dependency failure changes health status`
    - Assert that after `POST /fault/dependency-failure`, `GET /health` returns HTTP 503 with `{"status": "unhealthy", "reason": "dependency unavailable"}`
    - _Requirements: 9.1_

- [ ] 7. Checkpoint — run unit and property tests
  - Ensure all tests pass with `pytest tests/ -v --ignore=tests/test_integration.py`
  - Ask the user if any questions arise before proceeding.

- [ ] 8. Write integration tests
  - [ ] 8.1 Create `tests/test_integration.py`
    - Use `@pytest.mark.integration` marker
    - Start a real Uvicorn server on a random port using `anyio` / `uvicorn.Server` in an async fixture
    - Use `httpx.AsyncClient` pointed at the live server URL
    - Test full request/response cycle: root, health, slow-response with valid delay, fault/reset sequence
    - Verify `RequestLoggingMiddleware` emits JSON log lines to stdout (capture with `capsys` or log handler)
    - _Requirements: 1.1, 1.2, 1.3, 7.2, 9.4, 10.4_

  - [ ]* 8.2 Write property test for startup log fields (Property 3)
    - `# Feature: eks-github-cicd-app, Property 3: Startup log contains port and version`
    - Use `@given(st.integers(1024, 65535), st.text(min_size=1))` to start the app with various port/version combos and assert the first stdout line is valid JSON containing those values
    - _Requirements: 1.4_

- [ ] 9. Create Dockerfile
  - Write `Dockerfile` using `python:3.12-slim` base image
  - `ARG APP_VERSION=dev` → `ENV APP_VERSION=$APP_VERSION`
  - Create non-root user `appuser` (UID 1000), set `USER appuser`
  - `WORKDIR /app`, `COPY requirements.txt .`, `RUN pip install --no-cache-dir -r requirements.txt`
  - `COPY app/ ./app/`
  - `EXPOSE 8080`
  - `HEALTHCHECK --interval=10s --timeout=3s --start-period=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"`
  - `CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]`
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 10. Create Helm chart
  - [ ] 10.1 Create `helm/eks-github-cicd-app/Chart.yaml`
    - `apiVersion: v2`, `name: eks-github-cicd-app`, `version: 0.1.0`, `appVersion: "dev"`
    - _Requirements: 4.1_

  - [ ] 10.2 Create `helm/eks-github-cicd-app/values.yaml`
    - Include `replicaCount: 2`, `image.repository`, `image.tag: latest`, `image.pullPolicy: IfNotPresent`
    - `service.type: ClusterIP`, `service.port: 8080`
    - `resources.requests` and `resources.limits` for CPU and memory
    - `livenessProbe` and `readinessProbe` pointing to `/health` on port 8080
    - `serviceAccount.annotations` with `eks.amazonaws.com/role-arn: ""`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6_

  - [ ] 10.3 Create `helm/eks-github-cicd-app/templates/serviceaccount.yaml`
    - Kubernetes `ServiceAccount` with `metadata.annotations` from `values.serviceAccount.annotations`
    - _Requirements: 4.5_

  - [ ] 10.4 Create `helm/eks-github-cicd-app/templates/deployment.yaml`
    - `Deployment` with `spec.replicas: {{ .Values.replicaCount }}`
    - Container image `{{ .Values.image.repository }}:{{ .Values.image.tag }}`
    - `containerPort: 8080`
    - `livenessProbe` and `readinessProbe` from values
    - `resources` from values
    - `serviceAccountName` referencing the ServiceAccount
    - `env` block passing `APP_VERSION` from `image.tag`
    - _Requirements: 4.1, 4.3, 4.4, 4.5_

  - [ ] 10.5 Create `helm/eks-github-cicd-app/templates/service.yaml`
    - `Service` of type `{{ .Values.service.type }}` with `port: {{ .Values.service.port }}` targeting `containerPort: 8080`
    - _Requirements: 4.2_

  - [ ]* 10.6 Write property test for Helm values reflection (Property 12)
    - `# Feature: eks-github-cicd-app, Property 12: Helm chart values are reflected in rendered output`
    - Use `@given(st.integers(min_value=1, max_value=10), st.text(min_size=1))` for `replicaCount` and `image.tag`
    - Run `helm template` via `subprocess` with `--set` overrides and assert rendered YAML contains the expected values using `yaml.safe_load`
    - _Requirements: 4.1, 4.4, 4.6_

- [ ] 11. Create AWS infrastructure scripts
  - [ ] 11.1 Create `infra/01-create-ecr.sh`
    - `aws ecr create-repository --repository-name eks-github-cicd-app --region us-east-1`
    - Output the repository URI
    - _Requirements: 3.2_

  - [ ] 11.2 Create `infra/02-create-eks-cluster.sh`
    - `eksctl create cluster` with cluster name `eks-github-cicd-app`, region `us-east-1`, node type `t3.medium`, 2 nodes, Kubernetes 1.30
    - Enable OIDC provider: `eksctl utils associate-iam-oidc-provider`
    - _Requirements: 4.5_

  - [ ] 11.3 Create `infra/03-create-irsa-role.sh`
    - Create IAM policy granting `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer` on the ECR repo
    - Use `eksctl create iamserviceaccount` to create the IRSA role bound to the `eks-github-cicd-app` service account in the `default` namespace
    - Output the role ARN to be placed in `values.yaml`
    - _Requirements: 4.5_

  - [ ] 11.4 Create `infra/04-create-github-oidc-role.sh`
    - Create an IAM OIDC identity provider for `token.actions.githubusercontent.com`
    - Create an IAM role with trust policy scoped to `repo:dimwael/eks-github-cicd-app:ref:refs/heads/main`
    - Attach policies: `AmazonEC2ContainerRegistryPowerUser`, inline policy for `eks:DescribeCluster` and `eks:UpdateNodegroupConfig`
    - Output the role ARN to be set as `AWS_ROLE_ARN` in GitHub Actions
    - _Requirements: 3.5_

- [ ] 12. Create GitHub Actions workflows
  - [ ] 12.1 Create `.github/workflows/ci.yml`
    - Trigger: `pull_request` targeting `main`
    - Steps: `actions/checkout@v4`, `actions/setup-python@v5` (python 3.12), `pip install -r requirements.txt`, `pytest tests/ -v --ignore=tests/test_integration.py`
    - No AWS credentials, no Docker build, no deploy
    - _Requirements: 3.6_

  - [ ] 12.2 Create `.github/workflows/cd.yml`
    - Trigger: `push` to `main`
    - Permissions: `id-token: write`, `contents: read`
    - Steps:
      1. `actions/checkout@v4`
      2. `actions/setup-python@v5` + `pip install` + `pytest` (fail fast)
      3. `aws-actions/configure-aws-credentials@v4` with `role-to-assume: ${{ secrets.AWS_ROLE_ARN }}`, `aws-region: us-east-1`
      4. `aws-actions/amazon-ecr-login@v2`
      5. `docker build --build-arg APP_VERSION=${{ github.sha }} -t $ECR_REGISTRY/eks-github-cicd-app:${{ github.sha }} .`
      6. `docker push $ECR_REGISTRY/eks-github-cicd-app:${{ github.sha }}`
      7. `aws eks update-kubeconfig --name eks-github-cicd-app --region us-east-1`
      8. `helm upgrade --install eks-github-cicd-app ./helm/eks-github-cicd-app --set image.tag=${{ github.sha }} --set image.repository=$ECR_REGISTRY/eks-github-cicd-app --wait`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 13. Final checkpoint — wire everything together and deploy
  - [ ] 13.1 Create `.gitignore`
    - Exclude `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.hypothesis/`, `*.egg-info/`, `dist/`, `.env`
  - [ ] 13.2 Verify full test suite passes locally
    - Run `pytest tests/ -v --ignore=tests/test_integration.py` and confirm all tests pass
    - Ensure all tests pass, ask the user if questions arise.
  - [ ] 13.3 Initialize GitHub repository and push
    - `git init`, `git remote add origin https://github.com/dimwael/eks-github-cicd-app.git`
    - `git add .`, `git commit -m "feat: initial eks-github-cicd-app implementation"`
    - `git push -u origin main`
  - [ ] 13.4 Run AWS infrastructure scripts in order
    - Execute `infra/01-create-ecr.sh`, `infra/02-create-eks-cluster.sh`, `infra/03-create-irsa-role.sh`, `infra/04-create-github-oidc-role.sh`
    - Set `AWS_ROLE_ARN` secret in the GitHub repo settings
    - Update `helm/eks-github-cicd-app/values.yaml` with the IRSA role ARN output from script 03
  - [ ] 13.5 Trigger first deployment
    - Push a commit to `main` to trigger the `cd.yml` workflow
    - Verify the GitHub Actions run succeeds and the pod is running: `kubectl get pods`
    - Verify the application responds: `kubectl port-forward svc/eks-github-cicd-app 8080:8080` then `curl http://localhost:8080/health`

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation before moving to infrastructure
- Property tests use Hypothesis with `@settings(max_examples=100)`
- AWS Account: `649976227195`, Region: `us-east-1`, GitHub user: `dimwael`
- The `infra/` scripts are idempotent where possible but should be reviewed before re-running
