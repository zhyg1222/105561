$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$drive = $root.Substring(0, 1).ToLowerInvariant()
$wslRoot = "/mnt/$drive/" + (($root.Substring(2) -replace "\\", "/").TrimStart("/"))
$command = "for i in {1..30}; do cd '$wslRoot/deploy/compose' && docker compose --env-file .env up -d && exec sleep infinity; sleep 5; done"
$args = @("-d", "UbuntuAgent", "-u", "root", "--", "bash", "-lc", $command)
Start-Process -FilePath "C:\Windows\System32\wsl.exe" -ArgumentList $args -WindowStyle Hidden