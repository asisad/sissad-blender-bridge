"""Blender presence gates the existing tunnel; never launches an application."""


def lifecycle_action(*, blender_running, local_ready, runtime_running, retry_due):
    if not blender_running:
        return 'stop' if runtime_running else 'wait_blender'
    if not local_ready:
        return 'wait_local'
    if runtime_running:
        return 'observe'
    return 'connect' if retry_due else 'retry_wait'
