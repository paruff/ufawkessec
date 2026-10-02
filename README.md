# uFawkesSec (Archived)

**This repository is archived.** The security plane was merged into
[uFawkesPipe](https://github.com/paruff/uFawkesPipe): DefectDojo, Infisical,
the Trivy server and Falco now run with the CI/CD stack, alongside a
Conftest/Rego `policy-check` pipeline step. Open new issues and pull requests
there.

## Where things moved

| Was here                                                   | Now here (uFawkesPipe)                                                                                                         |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| DefectDojo, Infisical, Trivy server and Falco services     | [Security Plane](https://github.com/paruff/uFawkesPipe#-security-plane) in the README                                          |
| Rego policies and the policy guide                         | [`policy/`](https://github.com/paruff/uFawkesPipe/tree/main/policy) and [`docs/policy-guide.md`](https://github.com/paruff/uFawkesPipe/blob/main/docs/policy-guide.md) |
| CI security scanning                                       | [`.github/workflows/reusable-security-scanning.yml`](https://github.com/paruff/uFawkesPipe/blob/main/.github/workflows/reusable-security-scanning.yml) |

The previous README is in this repository's git history, before the commit
that archived it. The suite plan is at
[uFawkes.dev `docs/ai-sdlc/suite-release/`](https://github.com/paruff/uFawkes.dev/tree/main/docs/ai-sdlc/suite-release).
