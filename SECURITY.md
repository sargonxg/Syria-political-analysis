# Security and private research

The desk is an evolving single-operator application, not a multi-tenant production service. Anyone holding its shared key can access all cases. Keep databases, exports, backups and keys outside Git and protect their storage. The application does not encrypt the database or provide a tamper-proof audit ledger.

Use loopback access locally. Cloud operation requires a separate private-access boundary, HTTPS, persistent local storage and tested protected backups; see [deployment instructions](docs/deployment.md). Do not expose a local development setup publicly. No deployment is enabled by this repository.

For suspected vulnerabilities, use GitHub private vulnerability reporting if available. Otherwise open an issue requesting a private reporting channel without exploit details or sensitive material. Do not put credentials, private research or personal information in public issues. No external security certification or guaranteed response time is claimed.
