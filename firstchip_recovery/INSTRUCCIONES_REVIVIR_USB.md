# Guía Completa de Recuperación: Memoria USB FirstChip FC3281 / ZC3281

## 1. Resumen del Diagnóstico

- **Controlador:** FirstChip FC3281 / ZC3281 (Familia FC3379 / ZC3281 U3)
- **Vendor ID (VID):** `0x346D` (FirstChip Technology Limited)
- **Product ID (PID):** `0x3281` (ZC3281 / FC3281 USB Bootloader)
- **Serial Number:** `012345678901`
- **Estado Actual:** Modo ROM / Test Mode de Emergencia (0 Bytes / No Media / Sin Interfaz SCSI).

---

## 2. ¿Por qué ocurrió este error?

Durante operaciones de escritura a bajo nivel (como escribir una imagen ISO con `dd`, `Rufus` o interrupciones de energía/expulsión inesperada), si se corrompe el bloque de firmware o la tabla de traducción FTL en la memoria flash NAND:
1. El controlador no puede validar la firma digital del firmware al encender.
2. Como mecanismo de seguridad y recuperación de fábrica, el chip conmuta a la **ROM interna cableada en el silicio**.
3. En este modo de ROM, el dispositivo reporta su VID/PID genérico de fábrica (`0x346D` / `0x3281`), su número de serie genérico (`012345678901`) y 0 bytes de almacenamiento.

---

## 3. ¿Se puede revivir mediante comandos USB Reset (libusb / python / terminal)?

**Respuesta Técnica: NO.**

- Un comando de reset por bus USB (`libusb_reset_device`, `ioctl(fd, USBDEVFS_RESET)`, o apagar el puerto USB) sólo reinicia las líneas eléctricas D+/D- forzando una nueva re-enumeración USB.
- Al re-enumerar, el microcontrolador FirstChip vuelve a ejecutar el código de su ROM interna, intenta leer el firmware corrupto de la memoria NAND, vuelve a fallar y **regresa inmediatamente al modo ROM**.
- Ninguna instrucción de reseteo puede reconstruir las páginas de firmware dañadas en la memoria NAND.
- **La única forma física de revivir la memoria** es reprogramar el firmware utilizando la herramienta de producción en masa (**FirstChip U3 MpTool**), que está diseñada específicamente para comunicarse con el procesador en modo ROM y resintetizar el firmware.

---

## 4. Herramientas Preparadas en este Paquete

Hemos descargado, verificado y extraído todos los paquetes oficiales necesarios directamente en la carpeta:
`Documents/GSTEAMOS/firstchip_recovery/`

| Archivo / Carpeta | Descripción |
| :--- | :--- |
| `FCMptools_U3_20241101_3.10.14.8/` | Versión oficial estable de FirstChip U3 MpTool (Noviembre 2024) compatible con FC3379AA, FC3379BB, ZC3281AA y ZC3281BB. |
| `FCMptools_U3_20251210_3.31.24.14/` | Versión más reciente con soporte ampliado para chips NAND modernos de última generación. |
| `ChipGenius_v4_21_0701/` | Utilidad de diagnóstico de hardware para leer el Flash ID exacto de la NAND (Micron, Intel, Sandisk, Kioxia, YMTC). |
| `ABRIR_MPTOOL.bat` | Script de acceso directo para Windows que lanza el MpTool automáticamente con los permisos adecuados. |
| `LEEME_PRIMERO.txt` | Resumen rápido de instrucciones en texto plano para consultar en Windows. |
| `test_usb_reset.py` | Script demostrativo en Python que explica la interacción con libusb y la lógica del bootloader. |

---

## 5. Instrucciones Paso a Paso para Revivir la Memoria en Windows 11

### Paso 1: Conectar la Memoria
- Conecta la memoria USB en un puerto USB de la computadora (se recomienda un puerto USB 2.0 nativo o directo a la placa base, evitando hubs o extensiones).

### Paso 2: Abrir FirstChip U3 MpTool
- Abre la carpeta `firstchip_recovery\FCMptools_U3_20241101_3.10.14.8\`.
- Haz clic derecho sobre **`MpTools.exe`** y selecciona **"Ejecutar como administrador"**.
- (Alternativamente, puedes hacer doble clic en `ABRIR_MPTOOL.bat`).

### Paso 3: Detección Automática
- Al abrirse el programa, verás una cuadrícula con puertos numerados (Port 1 a Port 16).
- El puerto donde conectaste la memoria se iluminará automáticamente en color **AMARILLO o VERDE**.
- Verás el Flash ID de la memoria NAND (por ejemplo, una cadena hexadecimal como `2C C4 08 32 A6 00...`).

> **Nota sobre Contraseña:** Si entras en la pestaña **"Setting"**, el programa solicitará una contraseña. La contraseña de fábrica es **VACÍA** (simplemente deja el campo en blanco y haz clic en **OK**). Por lo general no es necesario modificar los parámetros por defecto ya que el modo automático detecta el chip NAND y selecciona el archivo de microcódigo adecuado (`code/3281AB/` o `code/3281BC/`).

### Paso 4: Iniciar el Flasheo
- Haz clic en el botón **`Start`** (o presiona la **barra espaciadora**).
- El software ejecutará el siguiente proceso automatizado:
  1. Carga del cargador ejecutable en la memoria SRAM del controlador FirstChip.
  2. Inicialización de los voltajes y timings de la memoria NAND.
  3. Escaneo y mapeo de bloques defectuosos (Bad Blocks scan).
  4. Flasheo del firmware nuevo en los bloques reservados de la NAND.
  5. Formateo a bajo nivel y creación del descriptor de almacenamiento masivo USB estándar.

### Paso 5: Finalización y Verificación
- El proceso suele tardar entre **60 y 180 segundos**.
- Una vez completado, el recuadro del puerto cambiará a color **VERDE BRILLANTE** indicando:
  - **`PASS`** o **`OK`**
  - La capacidad real restaurada (por ejemplo, `32GB`, `64GB`, etc.).
- Desconecta la memoria USB del puerto y vuelve a conectarla.
- Windows 11 emitirá el sonido característico de conexión USB y el explorador de archivos mostrará la unidad de almacenamiento completamente funcional y accesible.

---

## 6. Solución de Problemas Frecuentes

1. **El recuadro aparece en ROJO (Fail / Error):**
   - Si la versión 2024 da error de Flash ID no soportado, prueba la versión `FCMptools_U3_20251210_3.31.24.14`.
   - Entra en `Setting` (contraseña vacía) y en `Scan Mode`, cambia a `Normal Scan` o `Fast Scan`.
2. **El programa no detecta el pendrive:**
   - Desconecta y vuelve a conectar el pendrive en otro puerto USB.
   - Ejecuta `ChipGenius_v4_21_0701.exe` para confirmar que el puerto USB está reconociendo el bus VID `346D` PID `3281`.
