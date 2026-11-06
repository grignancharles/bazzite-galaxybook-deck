#!/bin/bash
set -euo pipefail

ISO="/Users/carlosgrinan/Downloads/bazzite-stable-amd64.iso"
DISK="/dev/disk8"
RDISK="/dev/rdisk8"

# Safety check
if /usr/sbin/diskutil list | grep -q "MessiEnto.*disk8"; then
    echo "ERROR: disk8 is MessiEnto! Aborting."
    exit 1
fi

echo "Unmounting disk8..."
/usr/sbin/diskutil unmountDisk "$DISK" || true

echo "Flashing ISO to $RDISK with dd..."
/bin/dd if="$ISO" of="$RDISK" bs=4194304

echo "Syncing writes..."
/bin/sync
echo "FLASHER_SUCCESS"
