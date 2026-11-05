# ReleaseGuard Security Baseline

## Secrets and credentials
Never commit credentials, private keys, tokens, passwords, connection strings, or signing material. Store secrets in a managed secret store and rotate exposed credentials. Findings should identify exact changed-file evidence without repeating secret values. Reference: https://owasp.org/www-project-top-ten/

## Transport security
TLS certificate verification must remain enabled for outbound HTTPS connections. Do not disable certificate validation to work around certificate errors. Use modern TLS defaults and validate service identities. Reference: https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html

## Input handling and code execution
Treat pull request content, filenames, comments, artifacts, and external responses as untrusted data. Avoid dynamic evaluation and shell execution with untrusted input. Validate inputs at trust boundaries and use parameterized APIs. Reference: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html

## Access control
Apply least privilege to service identities and API credentials. Separate read, write, and approval permissions. Approval actions must be attributable to an authenticated human reviewer. Reference: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
