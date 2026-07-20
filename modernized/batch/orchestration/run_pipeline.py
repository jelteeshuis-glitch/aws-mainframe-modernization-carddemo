#!/usr/bin/env python3
"""Local orchestrator for the CardDemo batch pipeline.

Runs LOAD -> POSTTRAN -> INTCALC -> COMBTRAN -> CREASTMT -> TRANREPT in strict order,
enforcing the dependencies through actual completion of each stage (never a timer). This
is the docker-compose / local equivalent of orchestration/step_functions.asl.json.

Usage:
    python orchestration/run_pipeline.py
"""

import sys

from carddemo_batch.cli import pipeline_main

if __name__ == "__main__":
    sys.exit(pipeline_main(sys.argv[1:]))
