# YYYY-MM-DD — <device> <setting>

**Setup**

- Device: MOZA AB9, firmware `<version>`, USB `346e:1000`
- Grip attached: `<none | MH16 | Alpha Prime | F-14>`
- Host: `<kernel>`, capture via `<usbmon bus N | tshark>`
- Cockpit version: `<version>` (VM `moza-win11`)

**Control changed**

Cockpit path, and the exact before → after values. One setting only.

**Baseline (idle) traffic**

The repeating poll pattern, so the diff below is readable.

**Frames observed**

```
→ 7e ..                      annotated
← 7e ..                      annotated
```

**Decode**

- direction / group / device id / command id
- payload encoding: type, endianness, scaling, range
- proposed command-table entry

**Verification**

- [ ] checksum `(sum + 13) & 0xFF` holds
- [ ] read-back on Linux returns what we wrote
- [ ] Cockpit UI shows our value after a Linux write
- [ ] physical/evdev effect matches expectation

**Confidence**: `observed | inferred | guessed`
**Safety**: `normal | destructive | forbidden`
