import torch


def is_gpu_available():
    return torch.cuda.is_available()


def is_valid_gpu_device(gpu_device):
    return gpu_device is not None and gpu_device > 0


def get_gpu_device(gpu_device):
    if gpu_device is None or gpu_device < 0:
        return -1

    if not is_gpu_available():
        return -1

    return gpu_device
