# ==============================================================================
# Variables de Entorno y Configuración Global para Intel Iris Xe G7 (96 EUs)
# Aplicadas a TODO el sistema operativo (Proton, Wine, Native, Gamescope)
# ==============================================================================

# 1. Mesa ANV (Vulkan) y Caché de Shaders Masiva en NVMe
export MESA_SHADER_CACHE_MAX_SIZE=20G
export ANV_GPL=true
export ANV_ENABLE_BUFFER_COMP=1
export mesa_glthread=true

# 2. DXVK y VKD3D-Proton optimizado a nivel global
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

# 4. CONFIGURACIÓN UNIVERSAL DE UPSCALING INTEL XeSS (DP4a) Y RENDER 720p -> 1080p
# Render Base: 1280x720 (Ahorra 56% de carga en GPU) -> Target: 1920x1080 QLED
export INTEL_XESS_DP4A=1
export XESS_FORCE_DP4A=1
export WINE_FULLSCREEN_FSR=1
export WINE_FULLSCREEN_FSR_STRENGTH=2
export WINE_FULLSCREEN_FSR_MODE=ultra
export SDL_VIDEODRIVER=wayland,x11

# Gamescope Global Target (1080p 60Hz nativo con escalador inteligente)
export GAMESCOPE_OUTPUT_WIDTH=1920
export GAMESCOPE_OUTPUT_HEIGHT=1080
export GAMESCOPE_OUTPUT_REFRESH=60
export GAMESCOPE_DEFAULT_RENDER_WIDTH=1280
export GAMESCOPE_DEFAULT_RENDER_HEIGHT=720
