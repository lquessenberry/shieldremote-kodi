# ShieldRemote Mapper — ARC-D joystick.xml notes

Physical buttons on the Anbernic **RG ARC-D** appear to Kodi as a **gamepad /
joystick**, not a keyboard. Map them once in Kodi’s controller configuration,
then (optionally) refine with a userdata keymap.

## 1. Controller profile

1. Kodi → Settings → System → Input → **Configure attached controllers**
2. Pick a gamepad profile close to Xbox 360 / generic
3. Bind ARC-D D-pad + face buttons (A B C X Y Z) + L1/L2/R1/R2 + Start/Select
4. There are **no analog sticks** — skip axis mapping

## 2. Example `joystick.xml` snippet

Copy to Kodi userdata `keymaps/joystick.xml` (merge carefully with existing
rules). Window id for the remote UI can be scoped later; global example:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<keymap>
  <global>
    <joystick name="Anbernic">
      <!-- Names vary by Android input device — check Kodi debug log -->
      <button id="1">Select</button>
      <button id="2">Back</button>
      <hat id="1" position="up">Up</hat>
      <hat id="1" position="down">Down</hat>
      <hat id="1" position="left">Left</hat>
      <hat id="1" position="right">Right</hat>
    </joystick>
  </global>
</keymap>
```

See: https://kodi.wiki/view/HOW-TO:Modify_joystick.xml

## 3. How this addon uses mappings

Profiles under `profiles/*.json` map **Kodi Action IDs** and joystick button
labels → **Android keycode names**. The remote WindowXML / service looks up
the active profile and calls `script.module.shieldremote.core` `send_key`.

**Limitation:** ATV Remote key injection is **not** a true HID gamepad — many
Shield games ignore remote-injected `KEYCODE_BUTTON_*`. This suite targets UI
nav + media keys, not game streaming.
