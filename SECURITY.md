# Security Policy

## Security Requirements

This section outlines the security measures and requirements that the ArduPilot
Methodic Configurator project implements to ensure the security and integrity
of our software.

### Dependency Management

We maintain secure software supply chains by keeping dependencies up-to-date:

- **Dependabot**: Automated dependency updates for GitHub ecosystem
- **Renovate**: Comprehensive dependency management across all package managers
- Regular monitoring and updates of Python packages and system dependencies

### Static Code Analysis

We use multiple static analysis tools to identify potential security issues and
ensure code quality:

- **[Ruff](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/ruff.yml)**:
  Fast Python linter and code formatter
- **[MyPy](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/mypy.yml)**:
  Static type checker for Python
- **[Pyright](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pyright.yml)**:
  Microsoft's Python type checker
- **[Pylint](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pylint.yml)**:
  Comprehensive Python code analyzer

### Automated Security Scanning

Our CI/CD pipeline includes automated security scans:

- **[GitHub CodeQL](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/codeql.yml)**:
  Advanced security vulnerability detection
- **[Dependency Review](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/dependency-review.yml)**:
  Automated review of dependency changes for security issues
- **[Anti-virus Scanning](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/gitavscan.yml)**:
  Regular malware detection using ClamAV
- **[OpenSSF Scorecard](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/scorecard.yml)**:
  Automated security health metrics

### Compliance and Best Practices

We adhere to industry standards and best practices as documented in our
[Compliance Guide](COMPLIANCE.md), including:

- Secure coding practices
- License compliance verification
- Regular security audits
- Open-source security guidelines

### What Users Can Expect

- **Secure Dependencies**: All dependencies are regularly updated and scanned for vulnerabilities
- **Code Quality**: Static analysis ensures adherence to security best practices
- **Vulnerability Response**: Prompt response to reported security issues (see below)
- **Transparency**: Public disclosure of security processes and findings

### Limitations

- **Third-party Dependencies**: Security depends on the security practices of our dependencies
- **User Environment**: Security of the end-user environment is outside our control
- **Configuration**: Improper configuration by users may introduce security risks
- **Physical Access**: Physical access to devices/flight controllers is not protected by this software

## Supported Versions

Only the latest version is supported with security updates.

## Reporting a Vulnerability

Select [security on the top of the github homepage](https://github.com/ArduPilot/MethodicConfigurator/security)
to [report a vulnerability](https://github.com/ArduPilot/MethodicConfigurator/security/advisories/new).

If we deem it relevant, we will try to fix it ASAP, or at least reply to you ASAP.

## Response Process

Once a vulnerability is reported, we will acknowledge receipt within 3 business days
and provide an estimated timeline for review and remediation.

## Public Disclosure

We kindly request that you do not publicly disclose the vulnerability until we have
had a reasonable opportunity to address it.
We aim to resolve vulnerabilities promptly and appreciate your cooperation in
maintaining the security of our users.

## Responsible Disclosure

We encourage responsible disclosure of security vulnerabilities.
Please provide detailed information about the vulnerability, including steps to
reproduce it, affected components, and potential impact.
This will help us to effectively address the issue.

<!-- Gurubase Widget -->
<script async src="https://widget.gurubase.io/widget.latest.min.js"
    data-widget-id="uE4kxEE4LY3ZSyfNsF5bU6gIOnWGTBOL_e16KwDH-0g"
    data-text="Ask AI"
    data-margins='{"bottom": "1rem", "right": "1rem"}'
    data-light-mode="true"
    id="guru-widget-id">
</script>
