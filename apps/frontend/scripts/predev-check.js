#!/usr/bin/env node
/**
 * predev guard: refuses to start a second `next dev` for THIS PostPiloter
 * frontend if one is already running (any port), instead of only checking
 * whether the default port is busy — the real incident that motivated this
 * was a second instance sitting on a different port, invisible to a
 * port-3000-only check.
 *
 * Never kills anything. If detection itself fails, it fails open (allows
 * `next dev` to proceed) rather than blocking a normal start.
 */
const { execFileSync } = require("child_process");
const path = require("path");

const FRONTEND_DIR = path.resolve(__dirname, "..");

function findRunningInstances() {
  // Escape single quotes for the PowerShell string literal.
  const escapedDir = FRONTEND_DIR.replace(/'/g, "''");
  const psScript = `
    $ErrorActionPreference = 'Stop'
    $dir = '${escapedDir}'
    $procs = Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
      Where-Object {
        $_.CommandLine -and $_.CommandLine.Contains($dir) -and (
          $_.CommandLine -like '*next*dev*' -or
          $_.CommandLine -like '*start-server.js*'
        )
      }
    $result = foreach ($p in $procs) {
      $ports = @(Get-NetTCPConnection -OwningProcess $p.ProcessId -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty LocalPort -Unique)
      [PSCustomObject]@{ Pid = $p.ProcessId; Ports = $ports; CommandLine = $p.CommandLine }
    }
    $result | ConvertTo-Json -Compress
  `;

  const raw = execFileSync(
    "powershell.exe",
    ["-NoProfile", "-NonInteractive", "-Command", psScript],
    { encoding: "utf8", timeout: 10000 }
  ).trim();

  if (!raw) return [];
  const parsed = JSON.parse(raw);
  return Array.isArray(parsed) ? parsed : [parsed];
}

function main() {
  let instances;
  try {
    instances = findRunningInstances();
  } catch (err) {
    console.warn(
      "[predev-check] Çalışan instance kontrolü yapılamadı, devam ediliyor:",
      err.message
    );
    return;
  }

  if (instances.length === 0) return;

  console.error("");
  console.error("========================================================");
  console.error(" PostPiloter frontend dev sunucusu ZATEN ÇALIŞIYOR.");
  console.error("========================================================");
  for (const inst of instances) {
    const ports = inst.Ports && inst.Ports.length ? inst.Ports.join(", ") : "bilinmiyor (henüz dinlemiyor olabilir)";
    console.error(`  PID: ${inst.Pid}  Port(lar): ${ports}`);
  }
  console.error("");
  console.error(" İkinci bir `next dev` süreci başlatmak, aynı .next klasörüne");
  console.error(" yazan iki bağımsız derleyici oluşturur ve bozuk chunk/404");
  console.error(" hatalarına yol açar (daha önce tam olarak bu yaşandı).");
  console.error("");
  console.error(" Ne yapmalısınız:");
  console.error("   - Zaten açık olan terminal/sekmeyi kullanın, YA DA");
  console.error("   - Eski süreci siz kontrollü şekilde kapatın, örneğin:");
  for (const inst of instances) {
    console.error(`       Stop-Process -Id ${inst.Pid}`);
  }
  console.error("     (Bu script hiçbir süreci otomatik olarak kapatmaz.)");
  console.error("========================================================");
  console.error("");
  process.exit(1);
}

main();
