from main import main as one_run
from core.scheduler import start_scheduler
from logger_setup import log


if __name__ == "__main__":
    log.info("Starting persistent mode (use Ctrl+C to stop)")
    start_scheduler(one_run)