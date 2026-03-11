from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from run_service_scripts.service_runtime import make_spring_petclinic_rest_config, run_stop


if __name__ == "__main__":
    raise SystemExit(run_stop(make_spring_petclinic_rest_config(), Path(__file__)))
