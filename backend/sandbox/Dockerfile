FROM python:3.12-slim

# Analysis tools and pytest. Project dependencies are installed into /deps at run time.
RUN pip install --no-cache-dir ruff bandit semgrep pytest pytest-asyncio

# Semgrep runs with no network, so the rules are baked in at build time.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && git clone --depth 1 https://github.com/semgrep/semgrep-rules /tmp/semgrep-rules \
 && mkdir -p /opt/rules \
 && cp -R /tmp/semgrep-rules/python /tmp/semgrep-rules/javascript /tmp/semgrep-rules/typescript /opt/rules/ \
 && find /opt/rules -type f ! \( -name '*.yaml' -o -name '*.yml' \) -delete \
 && find /opt/rules -name '*.test.yaml' -delete \
 && rm -rf /tmp/semgrep-rules /var/lib/apt/lists/* \
 && apt-get purge -y git \
 && chmod -R a+rX /opt/rules

# The sandbox also passes --user 10001:10001, so this just keeps the image consistent.
RUN useradd --uid 10001 --no-create-home sandbox
USER 10001:10001
WORKDIR /workspace