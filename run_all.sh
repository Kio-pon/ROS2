#!/bin/bash
# Root-level wrapper script to launch the simulator.
# Forwards execution and all arguments to the reorganized launchers/run_all.sh script.
exec "$(dirname "$0")/launchers/run_all.sh" "$@"
