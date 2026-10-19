param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'

try {
    $projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
    $expectedPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
    $entryPoint = Join-Path $projectRoot 'run.py'
    $servicePortText = $env:EDUPULSE_PORT
    $configPath = Join-Path $projectRoot '.env'
    if (-not $servicePortText -and (Test-Path -LiteralPath $configPath)) {
        foreach ($line in Get-Content -LiteralPath $configPath -Encoding UTF8) {
            if ($line.Trim() -match '^EDUPULSE_PORT\s*=\s*(.+)$') {
                $servicePortText = [Environment]::ExpandEnvironmentVariables($Matches[1].Trim().Trim('"').Trim("'"))
                break
            }
        }
    }
    if (-not $servicePortText) { $servicePortText = '8000' }
    $servicePort = 0
    if (-not [int]::TryParse($servicePortText, [ref]$servicePort) -or $servicePort -lt 1 -or $servicePort -gt 65535) {
        throw 'EDUPULSE_PORT is invalid. Check .env.'
    }
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq $servicePort | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($listeners.Count -eq 0) {
        Write-Host "EduPulse is not running on port $servicePort."
        exit 0
    }
    # Verify every listener before stopping anything. Never kill by python.exe name.
    $verified = @()
    foreach ($serviceProcessId in $listeners) {
        $serviceProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$serviceProcessId"
        if (-not $serviceProcess) { continue }
        $command = [string]$serviceProcess.CommandLine
        $hasEntry = $command -match '(?i)(?:^|[\\/\s"])run\.py(?:"?\s+(?:start)\s*$|"?\s*$)'
        $fromProject = $false
        $ancestor = $serviceProcess
        for ($i = 0; $i -lt 3 -and $ancestor; $i++) {
            if ([string]::Equals([string]$ancestor.ExecutablePath, $expectedPython, [StringComparison]::OrdinalIgnoreCase)) {
                $fromProject = $true
                break
            }
            if (-not $ancestor.ParentProcessId) { break }
            $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$($ancestor.ParentProcessId)"
        }
        # Absolute entry paths are also accepted, for direct Python startup.
        if ($command.IndexOf($entryPoint, [StringComparison]::OrdinalIgnoreCase) -ge 0) { $fromProject = $true }
        if (-not $hasEntry -or -not $fromProject) {
            throw "Port $servicePort is occupied by a process that cannot be verified as this EduPulse project (PID $serviceProcessId). Nothing was stopped."
        }
        $verified += $serviceProcess
    }
    foreach ($serviceProcess in $verified) {
        $serviceProcessId = [int]$serviceProcess.ProcessId
        if ($CheckOnly) {
            Write-Host "Verified EduPulse: port $servicePort, PID $serviceProcessId. Check only; nothing stopped."
            continue
        }
        # Recheck identity immediately before termination to avoid PID reuse.
        $current = Get-CimInstance Win32_Process -Filter "ProcessId=$serviceProcessId"
        if (-not $current) { continue }
        if ($current.CreationDate -ne $serviceProcess.CreationDate -or $current.CommandLine -ne $serviceProcess.CommandLine) {
            throw 'Process identity changed. Stop cancelled; try again.'
        }
        Stop-Process -Id $serviceProcessId -Force -ErrorAction Stop
        Wait-Process -Id $serviceProcessId -Timeout 10 -ErrorAction SilentlyContinue
        Write-Host "EduPulse stopped (PID $serviceProcessId)."
    }
    if (-not $CheckOnly) {
        $remaining = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq $servicePort)
        if ($remaining.Count) { throw "Port $servicePort is still in use. Restart was cancelled." }
        Write-Host 'Saved data and accounts are preserved. Use the launch BAT file to start again.'
    }
    exit 0
} catch {
    Write-Host "Unable to stop EduPulse: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'If access was denied, right-click the BAT file and choose Run as administrator.'
    exit 1
}
