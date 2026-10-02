# Corre o piloto no PC (IP português: a Betclic bloqueia os servidores do GitHub)
# e envia o livro de apostas; o push faz o GitHub reconstruir o site.
# Agendar (uma vez):  schtasks /Create /SC HOURLY /MO 2 /TN "TennisQuant Piloto" /TR "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File \"<caminho>\scripts\autopilot_local.ps1\""
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$log = Join-Path $root "work\autopilot_local.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
try {
    git pull --rebase --autostash -q origin master
    $env:PYTHONIOENCODING = "utf-8"
    & "$root\.venv\Scripts\python.exe" "$root\scripts\autopilot.py" | Out-File -Append -Encoding utf8 $log
    if ($LASTEXITCODE -ne 0) { throw "autopilot.py falhou ($LASTEXITCODE)" }
    git add artifacts/ledger.json artifacts/betclic_snapshot.json
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -q -m "chore: livro do piloto"
        git push -q origin master
    }
    Add-Content $log "$(Get-Date -Format s) ok"
} catch {
    Add-Content $log "$(Get-Date -Format s) ERRO: $_"
    exit 1
}
