# Security Policy

## Reporting a Vulnerability

If you believe you have found a security vulnerability, please email the project owner with details. Do not open a public issue with sensitive information.

- Include steps to reproduce, affected components/endpoints, and any PoC.
- We will acknowledge receipt within 72 hours and provide a remediation ETA.

## Secrets Management

- Do not commit any `.env` or secret values.
- Use platform-level secrets:
  - Render: Environment Variables
  - Vercel: Project Environment Variables
  - GitHub: Repository/Organization Secrets (Actions)


