"""Prefix script: switch the opened scene's Cycles renderer to the GPU (OptiX/CUDA) if available."""
import bpy
prefs = bpy.context.preferences.addons['cycles'].preferences
for kind in ('OPTIX', 'CUDA'):
    try:
        prefs.compute_device_type = kind
    except TypeError:
        continue
    prefs.get_devices()
    if any(d.type != 'CPU' for d in prefs.devices):
        for d in prefs.devices:
            d.use = d.type != 'CPU'
        bpy.context.scene.cycles.device = 'GPU'
        print('gpu_enable:', kind)
        break
