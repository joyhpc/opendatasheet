# Security Policy

## Scope

This repository contains extraction pipelines, validation tooling, generated device data, and CI/workflow metadata.

Use this policy for:
- exposed credentials or secrets
- vulnerabilities that could lead to unauthorized access or code execution
- supply-chain or dependency risks with realistic impact
- issues that could silently corrupt trusted generated outputs in a security-relevant way

## Reporting

Please report security issues privately to the maintainers before opening a public issue or pull request.

Until a dedicated private security inbox is added, use a private maintainer contact path and include:
- a short summary of the issue
- affected file(s), script(s), or workflow(s)
- reproduction steps or proof of impact
- any suggested mitigation, if available

## Do Not Post Publicly

To protect users and maintainers, do **not** post the following in public issues, PRs, or discussions:
- API keys, tokens, cookies, or credentials
- full secret values, even if you believe they are expired
- exploit steps that materially increase abuse risk before a fix is ready

If a secret is involved, redact it and rotate it first when possible.

## Supported Response Boundary

Maintainers will prioritize:
- credential exposure
- active security misconfiguration
- workflow or dependency issues with credible exploitability
- vulnerabilities affecting trusted export or validation paths

The following are usually **not** treated as security reports by themselves:
- general data quality problems without security impact
- feature requests
- speculative issues without a clear impact path
- support questions about local environment setup

## Disclosure Expectations

Please allow maintainers reasonable time to validate, mitigate, and release a fix before public disclosure.
Coordinated disclosure is preferred.
