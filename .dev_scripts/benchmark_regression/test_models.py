#!/usr/bin/env python
# Copyright (c) OpenMMLab. All rights reserved.

# This tool is used to update README.md and README_zh-CN.md in configs

import datetime
import glob
import os
import posixpath as osp  # Even on windows, use posixpath
import sys
import threading

import yaml

MMEditing_ROOT = osp.dirname(osp.dirname(osp.dirname(__file__)))
DOWNLOAD_DIR = osp.join(MMEditing_ROOT, 'work_dirs', 'download')
LOG_DIR = osp.join(
    MMEditing_ROOT, 'work_dirs',
    'benchmark_test_' + datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S'))
PARTITION = 'mm_lol'
START_PORT = 50000

sem = threading.Semaphore(8)  # The maximum number of restricted threads


def filter(info):
    """Filter the models you want to test.

    Args:
        info (dict): info of model.

    Returns:
        Bool: If this model should be tested.
    """

    # return 'liif' in info['Config']
    return True


def slurm_test(info: dict, thread_num):
    """Slurm test.

    Args:
        info (dict): Test info from metafile.yml
    """

    sem.acquire()

    config = info['Config']
    weights = info['Weights']
    basename, _ = osp.splitext(osp.basename(config))

    if osp.exists(DOWNLOAD_DIR):
        weights = osp.join(DOWNLOAD_DIR, 'hub', 'checkpoints',
                           osp.basename(weights))

    env_cmd = f'TORCH_HOME={DOWNLOAD_DIR} MASTER_PORT={thread_num+50000} '
    env_cmd += 'GPUS=1 GPUS_PER_NODE=1'
    base_cmd = 'bash tools/slurm_test.sh'
    task_cmd = f'{PARTITION} {basename}'
    out_file = osp.join(LOG_DIR, f'{thread_num:03d}_{basename}.log')
    cmd = f'{env_cmd} {base_cmd} {task_cmd} {config} {weights} &> {out_file}'

    print(f'RUN {thread_num:03d}: {cmd}')
    os.system(cmd)

    sem.release()


def test_models(meta_file):
    """Download all pth files.

    Args:
        pth_files (List[str]): List of pth files.
    """

    global thread_num

    with open(meta_file, 'r', encoding='utf-8') as f:
        data = f.read()
    yaml_data = yaml.load(data, yaml.FullLoader)

    for i in range(len(yaml_data['Models'])):
        if filter(yaml_data['Models']):
            threading.Thread(
                target=slurm_test,
                args=(yaml_data['Models'][i], thread_num)).start()
            thread_num += 1


if __name__ == '__main__':
    if len(sys.argv) <= 1:
        configs_root = osp.join(MMEditing_ROOT, 'configs')
        file_list = glob.glob(
            osp.join(configs_root, '**', '*metafile.yml'), recursive=True)
        file_list.sort()
    else:
        file_list = [
            fn for fn in sys.argv[1:] if osp.basename(fn) == 'metafile.yml'
        ]

    if not file_list:
        sys.exit(0)

    if not osp.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    thread_num = 0
    for fn in file_list:
        test_models(fn)