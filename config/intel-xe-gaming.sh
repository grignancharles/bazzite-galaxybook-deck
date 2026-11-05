#!/bin/bash
# Variables de Entorno Globales para Intel Iris Xe G7 (96 EUs) en Bazzite OS
# Diseñado para arquitectura Tiger Lake-UP3 (Gen12.1 / Xe-LP)

# 1. Mesa ANV (Vulkan) y Caché de Shaders Masiva en NVMe
export MESA_SHADER_CACHE_MAX_SIZE=20G
export ANV_GPL=true
export ANV_ENABLE_BUFFER_COMP=1
export INTEL_DEBUG=""
export mesa_glthread=true

# 2. DXVK y VKD3D-Proton optimizado para bus unificado LPDDR4x
export DXVK_ASYNC=1
export VKD3D_CONFIG=no_upload_hvv,force_static_cbv
export VKD3D_FEATURE_LEVEL=12_1
export PROTON_NO_ESYNC=0
export PROTON_NO_FSYNC=0
export WINE_LARGE_ADDRESS_AWARE=1

# 3. Forzar backend Vulkan y compatibilidad Wayland en Gamescope
export SDL_VIDEODRIVER=wayland,x11
export WINE_FULLSCREEN_FSR=1
export WINE_FULLSCREEN_FSR_STRENGTH=2

# 4. Habilitar soporte de DP4a para Intel XeSS en Wine/Proton
export INTEL_XESS_DP4A=1
