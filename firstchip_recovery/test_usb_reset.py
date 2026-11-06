#!/usr/bin/env python3
"""
Test USB Reset Tool for FirstChip FC3281 / ZC3281 (VID: 0x346D, PID: 0x3281)

Este script permite comprobar el estado USB del dispositivo FirstChip y explica
por qué un reset eléctrico (libusb_reset_device / IOCTL USBDEVFS_RESET) NO puede
recuperar la memoria cuando ha entrado en ROM Mode (0 bytes / Modo de Protección).
"""

import sys
import platform

VID_FIRSTCHIP = 0x346D
PID_FIRSTCHIP = 0x3281
BOOTLOADER_SN = "012345678901"

def print_explanation():
    print("=" * 70)
    print(" ANÁLISIS TÉCNICO: FIRSTCHIP FC3281 / ZC3281 EN MODO BOOTLOADER / ROM")
    print("=" * 70)
    print("""
1. ¿QUÉ SIGNIFICA VID=0x346D, PID=0x3281, SERIAL=012345678901?
   - Cuando un pendrive con controlador FirstChip (FC3379 / FC3281 / ZC3281)
     sufre una corrupción de firmware o interrupción de escritura a bajo nivel,
     el microcontrolador ASIC no puede cargar el microcódigo ISP desde los bloques
     reservados de la memoria NAND.
   - En este estado, la ROM interna del chip toma el control de emergencia.
   - La ROM expone por defecto:
       * VID: 0x346D (FirstChip Technology)
       * PID: 0x3281 (ZC3281 / FC3281)
       * Serial Number: 012345678901
       * Capacidad: 0 bytes (No Media / Sin capa de almacenamiento masivo)

2. ¿PUEDE UN COMANDO DE RESET USB (libusb / ioctl / terminal) ARREGLARLO?
   - NO. Un reset USB (eléctrico o por software) simplemente reinicia las líneas
     D+/D- del bus USB forzando una nueva enumeración.
   - Al reiniciarse, el procesador vuelve a ejecutar su ROM interna, intenta leer
     la NAND, detecta que la firma del firmware o la tabla FTL sigue dañada,
     y vuelve a caer de inmediato en ROM Mode (0x346D / 0x3281).
   - Un reset no puede reconstruir datos que están dañados en las celdas NAND.

3. ¿CÓMO SE REVIVE REALMENTE?
   - La ROM del FirstChip tiene una ventaja crítica: ACEPTA COMANDOS DE FÁBRICA.
   - La herramienta oficial FirstChip U3 MpTool inyecta un cargador en la SRAM
     del controlador, lee el Flash ID de la memoria NAND, flashea un nuevo
     firmware ISP en los bloques reservados, formatea a bajo nivel y devuelve
     el pendrive a su capacidad original (100% funcional).
""")
    print("=" * 70)

def try_usb_reset():
    print(f"Buscando dispositivo FirstChip VID: 0x{VID_FIRSTCHIP:04X}, PID: 0x{PID_FIRSTCHIP:04X}...")
    try:
        import usb.core
        import usb.util
    except ImportError:
        print("[!] pyusb no está instalado. Para instalarlo: pip install pyusb")
        return

    dev = usb.core.find(idVendor=VID_FIRSTCHIP, idProduct=PID_FIRSTCHIP)
    if dev is None:
        print(f"[-] No se encontró ningún dispositivo conectado con VID:0x{VID_FIRSTCHIP:04X} PID:0x{PID_FIRSTCHIP:04X}.")
        return

    print(f"[+] ¡Dispositivo FirstChip detectado!")
    try:
        print(f"    Fabricante: {dev.manufacturer}")
        print(f"    Producto:   {dev.product}")
        print(f"    Serial:     {dev.serial_number}")
    except Exception as e:
        print(f"    Info: {e}")

    print("[*] Enviando reset de bus USB (libusb_reset_device)...")
    try:
        dev.reset()
        print("[+] Reset enviado satisfactoriamente.")
        print("[!] Como se explicó arriba, el dispositivo se reinicia en ROM Mode")
        print("    porque requiere que FirstChip MpTool reprograme el firmware.")
    except Exception as e:
        print(f"[-] Error enviando reset: {e}")

if __name__ == "__main__":
    print_explanation()
    if "--reset" in sys.argv:
        try_usb_reset()
    else:
        print("Para intentar enviar una señal de reset por bus USB: python3 test_usb_reset.py --reset")
