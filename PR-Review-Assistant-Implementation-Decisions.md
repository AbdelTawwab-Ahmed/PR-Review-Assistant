# PR-Review-Assistant -- Implementation Decisions

## 1. Technology Stack

  Component                 Technology
  ------------------------- ------------------------------
  Programming Language      Python
  Agent Framework           LangGraph
  Backend                   FastAPI
  Frontend                  Streamlit
  Database                  PostgreSQL
  LLM                       Azure OpenAI
  GitHub Integration        GitHub API + Webhooks
  Tool Integration          Model Context Protocol (MCP)
  Code Execution            Docker / Cloud Sandbox
  Testing                   Pytest
  Code Quality & Security   Ruff / Bandit / Semgrep
  Containerization          Docker
  CI/CD                     GitHub Actions

## 2. Architecture & Execution

-   **Multi-Agent Architecture:** Use specialized agents, each
    responsible for a specific task.
-   **LangGraph:** Manage workflow execution, shared state, routing, and
    agent coordination.
-   **Parallel Processing:** Run independent analysis tasks concurrently
    to reduce execution time.
-   **Controlled Code Modification:** Organize code changes to prevent
    conflicting edits.
-   **Retry & Recovery:** Re-run relevant analysis or fixing steps when
    validation or tests fail.
-   **Human-in-the-Loop (HITL):** Require human approval before
    sensitive operations.
-   **Final Merge:** The final decision to merge a pull request always
    remains with the user.

## 3. GitHub Integration

The application will integrate with GitHub to:

-   Receive pull request events through webhooks.
-   Retrieve pull request metadata, changed files, and code diffs.
-   Analyze code changes and identify potential issues.
-   Publish review comments and analysis reports.
-   Implement approved changes and push them to the pull request branch.
-   Monitor pull request status, commits, and check results.

## 4. Code Execution & Security

-   Execute repository code inside an isolated environment.
-   Use Docker locally during development when the developer's machine
    has sufficient resources.
-   Use a cloud sandbox as the primary code-execution environment in
    production.
-   Restrict CPU, memory, storage, and execution time.
-   Restrict network access according to the task's requirements.
-   Prevent executed repository code from accessing application secrets
    or host credentials.
-   Treat repository content and execution output as untrusted input.

## 5. CI/CD

GitHub Actions will automate the build, testing, quality-checking, and
deployment processes.

The pipeline will:

1.  Run on pushes and pull requests.
2.  Install dependencies and run automated tests with Pytest.
3.  Run code-quality and security checks using Ruff, Bandit, and
    Semgrep.
4.  Build Docker images.
5.  Push approved images to Azure Container Registry (ACR).
6.  Deploy the application to Azure Container Apps.
7.  Maintain separate Development and Production environments.
8.  Require explicit approval before deploying to Production.

## 6. Azure Cloud Services

Azure services will be used where they provide clear value to the
application.

### 6.1 Core Services

  -----------------------------------------------------------------------
  Azure Service                       Purpose
  ----------------------------------- -----------------------------------
  Azure OpenAI                        Provides the language models used
                                      by the agents for code analysis,
                                      reasoning, and review tasks.

  Azure Application Insights          Collects application telemetry,
                                      traces, metrics, errors, and
                                      performance data.

  Azure Container Apps                Hosts and runs the backend and
                                      other containerized application
                                      services.

  Azure Container Registry (ACR)      Stores and manages the
                                      application's Docker images.

  Azure Key Vault                     Securely stores and manages API
                                      keys, credentials, and other
                                      application secrets.
  -----------------------------------------------------------------------

### 6.2 Optional Services

These services will be adopted based on application requirements,
expected workload, cost, and available development-machine resources.

  -----------------------------------------------------------------------
  Azure Service                       Potential Purpose
  ----------------------------------- -----------------------------------
  Azure Database for PostgreSQL       Hosts the application's PostgreSQL
                                      database as a managed cloud
                                      service.

  Azure Blob Storage                  Stores reports, artifacts, logs, or
                                      other files when persistent object
                                      storage is needed.

  Azure Container Apps Dynamic        Provides isolated, on-demand
  Sessions                            execution environments for
                                      untrusted repository code, subject
                                      to suitability and service
                                      constraints.
  -----------------------------------------------------------------------

## 7. Performance & Cost Optimization

-   **Parallel Execution:** Run independent agent tasks concurrently
    where possible.
-   **Caching:** Cache reusable results to avoid repeated API calls,
    model requests, and analysis work.
-   **Controlled Concurrency:** Limit simultaneous agent runs and
    external requests to protect resources and control costs.
-   **Model Selection:** Choose the most suitable Azure OpenAI model for
    each task, balancing quality, latency, and cost.
-   **Monitoring:** Track latency, token usage, model calls, failures,
    and estimated costs.
-   **Resource Limits:** Apply appropriate limits to containers and
    sandbox workloads.

## 8. Git Branching Strategy

-   Create a separate branch for each task or major component, such as
    `ai`, `backend`, and `frontend`.
-   Do not develop directly on the `main` branch.
-   Keep each task's implementation and tests isolated in its dedicated
    branch.
-   Open a Pull Request when a task is ready for integration.
-   Run the required tests and quality checks before merging.
-   Merge into `main` only after review and approval.
-   Keep branches focused and regularly synchronize them with the target
    branch to reduce integration conflicts.

## 9. Architecture Principles

The project will follow **Clean Architecture** and maintain a
professional, modular codebase.

Key principles:

-   Separate business rules from frameworks, infrastructure, and
    external services.
-   Keep domain logic independent of FastAPI, LangGraph, databases, and
    cloud providers wherever practical.
-   Define clear interfaces (ports) for external dependencies and
    implement them in the infrastructure layer.
-   Keep application use cases responsible for coordinating business
    workflows.
-   Use dependency injection to make components testable and
    replaceable.
-   Write unit, integration, and end-to-end tests for the appropriate
    layers.
-   Apply consistent naming, typing, documentation, error handling, and
    logging.
-   Keep security, observability, maintainability, and testability as
    first-class design concerns.

------------------------------------------------------------------------

## 10. Key Project Principles

1.  The system assists with pull request review and controlled changes;
    it does not make the final merge decision.
2.  Sensitive actions must be protected by human approval.
3.  Repository code must execute in an isolated and resource-limited
    environment.
4.  Production execution should use a cloud sandbox rather than relying
    on a developer's local machine.
5.  Azure services should be introduced according to actual
    requirements, with optional services evaluated for cost and
    operational complexity.
6.  Every component should be independently testable and maintainable.
7.  Security, reliability, performance, and cost awareness must guide
    implementation decisions.
