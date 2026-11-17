# HIVE Emulation Workspace

Purpose:
A controlled environment for evaluating experimental capabilities
before considering integration into the stable HIVE application.

## Directory structure

- prototypes/: Experimental implementations.
- experiments/: Experiment definitions and procedures.
- tests/: Isolated tests for experimental capabilities.
- reports/: Test results, evidence, and validation decisions.

## Required development lifecycle

1. Define the proposed capability.
2. Build a prototype without modifying HIVE Core.
3. Test the prototype in this workspace.
4. Record results and supporting evidence.
5. Review security, reliability, and compatibility.
6. Obtain explicit approval before integrating anything into hive/.
7. Run the complete production test suite after approved integration.

## Safety rules

- Experimental code is not production code.
- No automatic integration into HIVE Core.
- Do not execute untrusted code without an appropriate sandbox.
- Do not use production credentials or live accounts in experiments.
- Preserve existing production tests and backups.
- Record failures as well as successes.
