#!/bin/bash
# ==============================================================================
# Variables de Entorno y Configuración Global para Intel Iris Xe G7 (96 EUs)
# Aplicadas a TODO el sistema operativo (Proton, Wine, Native, Gamescope)
# ==============================================================================

# 1. Mesa ANV (Vulkan) y Caché de Shaders Masiva en NVMe
export MESA_SHADER_CACHE_MAX_SIZE=20G
export ANV_GPL=true
export ANV_ENABLE_BUFFER_COMP=1
export INTEL_DEBUG=""
export mesa_glthread=true

# 2. DXVK y VKD3D-Proton optimizado a nivel global (Sin necesitar configurar juego por juego)
export DXVK_ASYNC=1
export DXVK_CONFIG_FILE=/etc/dxvk.conf
export VKD3D_CONFIG_FILE=/etc/vkd3d.conf
export VKD3D_CONFIG=no_upload_hvv,force_static_cbv
export VKD3D_FEATURE_LEVEL=12_1
export PROTON_NO_ESYNC=0
export PROTON_NO_FSYNC=0
export WINE_LARGE_ADDRESS_AWARE=1

# 3. Fallback Global de Mesh Shaders a Compute Shaders para TODOS los juegos D3D12/UE5
export VKD3D_DISABLE_EXTENSIONS="VK_EXT_mesh_shader"

# 4. Forzar backend Vulkan y compatibilidad Wayland en Gamescope
export SDL_VIDEODRIVER=wayland,x11
export WINE_FULLSCREEN_FSR=1
export WINE_FULLSCREEN_FSR_STRENGTH=2

# 5. Habilitar aceleración por hardware DP4a (Intel XeSS) en Wine/Proton
export INTEL_XESS_DP4A=1
