"""Quick smoke test: 3 reefs, 10 particles each, 5 days."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import run_connectivity as rc

# Override config for smoke test
rc.N_PARTICLES_PER_REEF = 10
rc.SIM_DAYS = 5
rc.DT_HOURS = 2.0

# Monkey-patch reefs to first 3
from reef_definitions import load_reefs
import reef_definitions
orig_load = reef_definitions.load_reefs
reef_definitions.load_reefs = lambda p=None: orig_load(p)[:3]
rc.load_reefs = reef_definitions.load_reefs

rc.main()
