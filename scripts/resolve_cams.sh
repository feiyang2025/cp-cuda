#!/bin/bash
# resolve_cams.sh — 按 v4l2 设备名解析摄像头节点号并输出 export 语句。
# v4l2 节点号(/dev/videoN)会随 USB 枚举/GMSL 驱动加载顺序漂移,不能硬编码。
# 设备名(来自 /sys/class/video4linux/videoN/name),本机 T906G 实测:
#   twgmsl 9-002a  -> GMSL 120° 广角(主路 road, 实测 /dev/video1)
#   twgmsl 10-0028 -> GMSL  60° 窄角(wide,      实测 /dev/video2)
#   其余 twgmsl 口(9-0028/10-002a/11-*/12-*) 本机未接相机 -> 不选
#   USB Camera     -> USB IMX678 90°(后备)
# 关键: FOV 由插在哪个 GMSL 口上的镜头决定, 与传感器 i2c 地址(0028/002a)无关。
#   2026-10-14 目视预览确认: /dev/video1(9-002a)=120° 更广, /dev/video2(10-0028)=60° 更窄;
#   而 /dev/video0(9-0028) 驱动报 disconnected(该口没接相机), 不能再当 road。
#   换口/换接线后必须同步改这里的设备名。
# 内参: 角色 road=120°(fl≈961.76) / wide=60°(fl=1740) 不变(camera.py 按角色给 fl)。
# 输出: export ROAD_CAM='N' 等(与 launch_env.sh 的用法一致)
#
# 容错优先级:
#   ROAD   = 120°(若死则用 USB)
#   WIDE   = 60°(若死则用 USB)
#   DRIVER = USB(仅当 ROAD/WIDE 未占用 USB 时)

find_by_name() {
  local pat="$1"
  for d in /sys/class/video4linux/video*; do
    [ -d "$d" ] || continue
    if grep -q "$pat" "$d/name" 2>/dev/null; then
      echo "/dev/$(basename "$d")"
      return 0
    fi
  done
  return 1
}

CAM120=$(find_by_name "twgmsl 9-002a")
CAM60=$(find_by_name "twgmsl 10-0028")
CAMUSB=$(find_by_name "USB Camera")

ROAD=""
WIDE=""
DRIVER=""

# 120° 广角做主路
if [ -n "$CAM120" ]; then
  ROAD="$CAM120"
else
  ROAD="$CAMUSB"
fi
# 60° 窄角做 wide
if [ -n "$CAM60" ]; then
  WIDE="$CAM60"
elif [ -n "$CAMUSB" ] && [ "$CAMUSB" != "$ROAD" ]; then
  WIDE="$CAMUSB"
fi
# USB 作为第三路(仅当 ROAD 不是 USB 时才有独立意义;否则留空避免重复)
if [ -n "$CAMUSB" ] && [ "$CAMUSB" != "$ROAD" ] && [ "$CAMUSB" != "$WIDE" ]; then
  DRIVER="$CAMUSB"
fi

echo "export ROAD_CAM='${ROAD#/dev/video}'"
echo "export WIDE_CAM='${WIDE#/dev/video}'"
echo "export DRIVER_CAM='${DRIVER#/dev/video}'"
