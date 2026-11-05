#!/bin/bash
# ==============================================================================
# Configuración del Túnel Nativo Permanente de iPhone (Sin botones manuales)
# ==============================================================================

set -euo pipefail

# Eliminar cualquier acceso directo manual previo si existiera
rm -f /usr/share/applications/iphone-tunnel-*.desktop

# Enlace simbólico de utilidad en /usr/bin
ln -sf /usr/libexec/galaxybook-iphone-tunnel.sh /usr/bin/iphone-tunnel
