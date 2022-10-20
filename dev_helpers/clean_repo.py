from pathlib import Path

import os
import glob
import shutil
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_repo():
    remove_files = './build ./dist'.split(' ')
    _ = [shutil.rmtree(Path(path)) for path in remove_files if os.path.exists(path)]
    if os.path.exists(Path(glob.glob(os.path.normpath(os.path.join('.', './*.egg-info')))[0])):
        shutil.rmtree(Path(glob.glob(os.path.normpath(os.path.join('.', './*.egg-info')))[0]))


if __name__ == "__main__":
    clean_repo()
