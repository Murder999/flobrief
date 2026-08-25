#!/usr/bin/env python
"""predev guard: refuses to start a second `uvicorn` for THIS PostPiloter
backend if one is already running, mirroring apps/frontend/scripts/predev-check.js.

Detects by process command line (backend directory path + "uvicorn"), not by
port, since a duplicate instance can end up on a different port. Never kills
anything. If detection itself fails, it fails open.
"""

import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = str(Path(__file__).resolve().parent.parent)


def find_running_instances():
    escaped_dir = BACKEND_DIR.replace("'", "''")
    ps_script = f"""
    $ErrorActionPreference = 'Stop'
    $dir = '{escaped_dir}'
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
      Where-Object {{
        $_.CommandLine -and $_.CommandLine.Contains($dir) -and $_.CommandLine -like '*uvicorn*'
      }}
    $result = foreach ($p in $procs) {{
      $ports = @(Get-NetTCPConnection -OwningProcess $p.ProcessId -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty LocalPort -Unique)
      [PSCustomObject]@{{ Pid = $p.ProcessId; Ports = $ports }}
    }}
    $result | ConvertTo-Json -Compress
    """
    raw = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    ).stdout.strip()

    if not raw:
        return []
    import json

    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else [parsed]


def main() -> int:
    try:
        instances = find_running_instances()
    except Exception as err:  # noqa: BLE001 - fail open on any detection error
        print(f"[predev_check] Çalışan instance kontrolü yapılamadı, devam ediliyor: {err}")
        return 0

    if not instances:
        return 0

    print("")
    print("========================================================")
    print(" PostPiloter backend (uvicorn) ZATEN ÇALIŞIYOR.")
    print("========================================================")
    for inst in instances:
        ports = inst.get("Ports") or []
        ports_str = (
            ", ".join(str(p) for p in ports) if ports else "bilinmiyor (henüz dinlemiyor olabilir)"
        )
        print(f"  PID: {inst.get('Pid')}  Port(lar): {ports_str}")
    print("")
    print(" İkinci bir uvicorn süreci başlatmak, aynı porta iki bağımsız")
    print(" sunucunun bağlanmaya çalışmasına ve tutarsız/çakışan davranışa")
    print(" yol açar (daha önce tam olarak bu yaşandı).")
    print("")
    print(" Ne yapmalısınız:")
    print("   - Zaten açık olan terminal/sekmeyi kullanın, YA DA")
    print("   - Eski süreci siz kontrollü şekilde kapatın, örneğin:")
    for inst in instances:
        print(f"       Stop-Process -Id {inst.get('Pid')}")
    print("     (Bu script hiçbir süreci otomatik olarak kapatmaz.)")
    print("========================================================")
    print("")
    return 1


if __name__ == "__main__":
    sys.exit(main())
