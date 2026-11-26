# RPLIDAR for TouchDesigner (Windows)

A self-contained TouchDesigner component for Slamtec RPLIDAR 2D lidars:
scanning, background learning, people detection and tracking, zones, a
projection mask and OSC.

- `rplidar.tox` – the component. Drop it into any project.
- `rplidar_examples.toe` – the component plus five small examples.

Nothing to install. The driver is plain Python inside the component's DATs: it
opens the COM port through the Windows API (`kernel32` via `ctypes`) and uses
`numpy`, which ships with TouchDesigner. No pip, no pyserial, no installer.

## Requirements

- Windows 10 or 11. Does not run on macOS (the driver uses Win32).
- [TouchDesigner](https://derivative.ca/download); the free Non-Commercial
  licence is enough. Saved with 2025.32460; older builds may refuse to open it.
- An RPLIDAR that talks at 115200 baud: **A1** or **A2M8** (tested on A2M8,
  firmware 1.27). A2M12, A3 and the S series use faster baud rates and are not
  supported.
- A USB cable that carries data, not just power.

The lidar's USB adapter is a Silicon Labs CP210x. Windows 10/11 normally
installs its driver from Windows Update the first time it is plugged in. If no
COM port appears at all, install the
[CP210x VCP driver](https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers).

The A1 often needs a separate 5 V supply; on USB power alone the motor may spin
too slowly.

## Quick start

1. Plug in the lidar. The head should start spinning.
2. Drag `rplidar.tox` into a TouchDesigner network (or open `rplidar_examples.toe`).
3. Step out of range. After 3 s of scanning the component learns the empty room
   as its background (3 s). The node shows a top-down view straight away.

The port is found automatically. If someone was in the room while it learned,
pulse **Learn Background** again once it is empty.

The `status` DAT inside the component shows the live state:

```
RUNNING  port COM10  mode express
driver: scanning
rpm: 422   revs: 118   samples: 63936   errors: 0
sensor: RPLIDAR A2M8 / A2, firmware 1.27, hardware 5

BACKGROUND: learned (508 bins with a wall)
```

The background is stored in the `bg_data` DAT and saved with your project.
Relearn it after moving the sensor or the furniture.

## Outputs

Everything except `out5`, `out6` and `out8` only counts what is inside the
**area**: a rectangle in metres set on the *Area* page (pulse **Fit Area to
Room** to fit it to the learned background). Inside the area, position is also
given as `u`, `v` from 0 to 1, ready for a TOP's Translate. Objects narrower
than *Person Min Width* or younger than *Person Min Age* are ignored.

| Output | |
|---|---|
| `out1_person` | CHOP, the person seen longest: `present x y u v speed id` |
| `out2_people` | CHOP, one sample per person: `active id x y u v width age speed` – for instancing |
| `out3_count` | CHOP: `count`, `enter` / `exit` (1 for one frame) – for a CHOP Execute DAT |
| `out4_zones` | CHOP, one channel per row of `zones_table` (`u0 u1 v0 v1`), value = people in the zone |
| `out5_info` | CHOP: `ok rpm revs samples errors objects points background learning` |
| `out6_view` | TOP, top-down view with area and zones |
| `out7_mask` | TOP, soft white blobs under people; the whole image is the area |
| `out8_cloud` | TOP 512×1 RGBA32F, every scan point: `R`=x `G`=y [m], `B`=distance, `A`=1 return / 2 object |

The `OUTPUTS` DAT inside the component has the same description.

Coordinates: `x` to the right of the sensor, `y` forward, in metres. Angle 0 is
the sensor's front.

### Examples (`rplidar_examples.toe`)

1. A circle follows a person – `out1_person`, Translate = `u - 0.5`, `v - 0.5`.
2. People counter – `out3_count` into a Text TOP.
3. Zones – `out4_zones` as pixels; an occupied zone lights up.
4. Trails – `out7_mask` through a feedback loop.
5. One instance per person – `out2_people` driving a Geometry COMP.

Each example has a note next to it.

## Parameters

**Lidar** – Active (off releases the COM port), Port (`auto` or e.g. `COM10`),
Find Port, Motor Speed (PWM 0–1023, default 400 ≈ 450 rpm), Express Scan,
Restart Driver.

**Background** – Learn Background on Start, Learn Background, Learn Time,
Clear Background, Use Background, Background Margin (mm closer than the wall
something must be to count), Range Min / Max, Object Min / Max Width (bins),
Allowed Gap, Front Surface Depth.

**Area** – Fit Area to Room, area bounds in metres, Person Min Width / Min Age,
Flip u / Flip v, mask blob radius and resolution.

**Tracking** – Slots, Max Jump per Frame, Release ID After, Position Smoothing.

**View** – range, show background / objects. **OSC** – Send OSC, host, port;
the `objects` channels are sent with their names as addresses.

## Motor speed and resolution

The lidar takes a fixed 4000 samples/s whatever the speed, so a slower head
gives more samples per revolution:

| Speed | Samples / rev | Resolution |
|---|---|---|
| 810 rpm (PWM 660, factory) | ~296 | 1.2° |
| 450 rpm (PWM 400, default here) | ~540 | 0.67° |

Hence 512 bins. At 810 rpm a hand at 2 m is one or two samples – not
distinguishable from noise. Raise the PWM if you need faster updates for fast
movement.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `NOT CONNECTED`, head spinning | Another program or a second TouchDesigner has the port. COM ports are exclusive |
| No COM port at all | USB adapter driver missing (see Requirements) or a charge-only cable |
| Port found, sensor does not answer | Unsupported model (A2M12 / A3 / S series), or a charge-only cable |
| Head not spinning or under 200 rpm | Power: plug straight into the computer or a powered hub; the A1 needs 5 V |
| Objects where nobody is | Lower Range Max or raise Background Margin, then relearn |
| Only part of the 360° is visible | Something is blocking the head |
| Black, glass and mirror surfaces missing | Lidar physics; reposition the sensor |
| Head keeps spinning after TouchDesigner crashed | Unplug and replug the USB |

## Licence

MIT © 2026 technofania. The protocol was implemented from Slamtec's public
*RPLIDAR Interface Protocol* documentation and
[rplidar_sdk](https://github.com/Slamtec/rplidar_sdk); no Slamtec code is
included. No drivers are bundled or redistributed.
