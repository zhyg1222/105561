$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "D:\yige-personal-kb\.runtime\backups\drill-$stamp"
$wslDir = "/mnt/d/yige-personal-kb/.runtime/backups/drill-$stamp"
$db = "xiaojuju_restore_$stamp"
if ($db -notmatch '^xiaojuju_restore_[0-9]{8}_[0-9]{6}$') { throw "invalid temporary database name" }
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

function Invoke-Wsl([string]$Command) {
    $output = wsl.exe -d UbuntuAgent -u root -- bash -lc $Command
    if ($LASTEXITCODE -ne 0) { throw "WSL command failed: $Command`n$output" }
    return ($output -join "`n").Trim()
}

$result = [ordered]@{
    stamp = $stamp
    postgres = $null
    neo4j = $null
    cleanup = $null
}
$dbCreated = $false
try {
    $dumpInContainer = "/tmp/xjj-drill-$stamp.dump"
    Invoke-Wsl "docker exec xiaojuju-agent-postgres-1 pg_dump -Fc -U xiaojuju -d xiaojuju -f $dumpInContainer" | Out-Null
    Invoke-Wsl "docker cp xiaojuju-agent-postgres-1:$dumpInContainer '$wslDir/postgres.dump'" | Out-Null

    Invoke-Wsl "docker exec xiaojuju-agent-postgres-1 createdb -U xiaojuju $db" | Out-Null
    $dbCreated = $true
    $restoreInContainer = "/tmp/xjj-restore-$stamp.dump"
    Invoke-Wsl "docker cp '$wslDir/postgres.dump' xiaojuju-agent-postgres-1:$restoreInContainer" | Out-Null
    Invoke-Wsl "docker exec xiaojuju-agent-postgres-1 pg_restore -U xiaojuju -d $db --no-owner --no-privileges $restoreInContainer" | Out-Null

    $countSql = "select (select count(*) from app_events), (select count(*) from app_memory_candidates), (select count(*) from app_outbox), (select count(*) from app_approvals);"
    $restored = Invoke-Wsl "docker exec xiaojuju-agent-postgres-1 psql -U xiaojuju -d $db -At -c '$countSql'"
    $source = Invoke-Wsl "docker exec xiaojuju-agent-postgres-1 psql -U xiaojuju -d xiaojuju -At -c '$countSql'"
    if ($restored -ne $source) { throw "postgres row-count mismatch: source=$source restored=$restored" }
    $result.postgres = [ordered]@{ source_counts = $source; restored_counts = $restored; dump_bytes = (Get-Item "$backupDir\postgres.dump").Length }

    $neo4jBackup = "D:\yige-personal-kb\.runtime\backups\drill-$stamp\neo4j.json"
    $python = "D:\yige-personal-kb\xiaojuju\.venv\Scripts\python.exe"
    $neo4jDump = & $python scripts\neo4j_logical_backup.py --backup $neo4jBackup
    if ($LASTEXITCODE -ne 0) { throw "neo4j backup failed" }
    $neo4jRestore = & $python scripts\neo4j_logical_backup.py --restore $neo4jBackup --group "restore_$stamp"
    if ($LASTEXITCODE -ne 0) { throw "neo4j restore failed" }
    $result.neo4j = [ordered]@{ backup = $neo4jDump; restore = $neo4jRestore; file = $neo4jBackup }

    $resultPath = Join-Path $backupDir "result.json"
    [System.IO.File]::WriteAllText($resultPath, ($result | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
    $result | ConvertTo-Json -Depth 8
}
finally {
    if ($dbCreated) {
        try { Invoke-Wsl "docker exec xiaojuju-agent-postgres-1 dropdb --if-exists -U xiaojuju $db" | Out-Null; $result.cleanup = "temporary_database_dropped" }
        catch { $result.cleanup = "temporary_database_cleanup_failed: $($_.Exception.Message)" }
        $resultPath = Join-Path $backupDir "result.json"
        [System.IO.File]::WriteAllText($resultPath, ($result | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
    }
}