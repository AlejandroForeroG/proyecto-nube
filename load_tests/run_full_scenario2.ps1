Param(
  [string]$Region = "us-east-1",
  [string]$Cluster = "proyecto-nube",
  [string]$ServiceWorker = "proyecto-nube-worker",
  [string]$WorkerFamily = "proyecto-nube-worker",
  [string]$WorkerContainer = "worker",
  [string]$Bucket = "miso-proyecto-nube-3",
  [string]$S3Prefix = "uploads",
  [string]$ResultsDir = "load_tests/results",
  [string[]]$Sizes = @("50","100"),
  [int[]]$Concurrencies = @(1,2,4),
  [string[]]$Modes = @("burst","sustained"),
  [switch]$SkipUpdateConcurrency,
  [switch]$GenerateVideos,           # genera y sube videos si faltan
  [int]$SustainedRate50 = 20,
  [int]$SustainedRate100 = 15
)

$ErrorActionPreference = "Stop"

function Assert-Command($name) {
  if (!(Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Comando requerido no encontrado: $name"
  }
}

function Ensure-Dir($path) {
  if (!(Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Preflight {
  Write-Host "==> Preflight checks" -ForegroundColor Cyan
  Assert-Command python
  Assert-Command aws
  if ($GenerateVideos) { Assert-Command ffmpeg }
  if (!(Test-Path "requirements.txt")) {
    Write-Warning "requirements.txt no encontrado en el cwd. Asegúrate de ejecutar este script desde la raíz del proyecto."
  }
  if (!$env:DATABASE_URL) { Write-Warning "DATABASE_URL no está definido en el entorno. inject_worker_tasks/compute_worker_metrics lo requerirán." }
  if (!$env:AWS_REGION) { $env:AWS_REGION = $Region }
  if (!$env:STORAGE_BACKEND) { $env:STORAGE_BACKEND = "s3" }
  if (!$env:SQS_QUEUE_NAME) { $env:SQS_QUEUE_NAME = "cola-nube" }
  Ensure-Dir $ResultsDir
}

function Ensure-S3Video([int]$sizeMb) {
  $key = "$S3Prefix/test_video_${sizeMb}MB.mp4"
  $uri = "s3://$Bucket/$key"
  $exists = (aws s3 ls $uri --region $Region 2>$null) -ne $null
  if ($exists) { return $uri }
  if (-not $GenerateVideos) {
    throw "No existe $uri y -GenerateVideos no fue especificado. Sube el archivo o ejecuta con -GenerateVideos."
  }
  Write-Host "  Generando video sintético ${sizeMb}MB y subiendo a $uri ..." -ForegroundColor Yellow
  $tmp = Join-Path $env:TEMP "test_videos"
  Ensure-Dir $tmp
  $out = Join-Path $tmp ("test_video_{0}MB.mp4" -f $sizeMb)
  $duration = 60
  if ($sizeMb -le 50) {
    ffmpeg -y -f lavfi -i "testsrc=duration=$duration:size=1280x720:rate=30" `
      -f lavfi -i "sine=frequency=440:duration=$duration" `
      -c:v libx264 -preset ultrafast -b:v 6500k -c:a aac -b:a 128k $out | Out-Null
  } else {
    ffmpeg -y -f lavfi -i "testsrc=duration=$duration:size=1920x1080:rate=30" `
      -f lavfi -i "sine=frequency=440:duration=$duration" `
      -c:v libx264 -preset ultrafast -b:v 13000k -c:a aac -b:a 128k $out | Out-Null
  }
  aws s3 cp $out $uri --region $Region | Out-Null
  return $uri
}

function Wait-EcsServiceStable([string]$cluster,[string]$service,[int]$timeoutSec=900) {
  $start = Get-Date
  while ((Get-Date) - $start -lt [TimeSpan]::FromSeconds($timeoutSec)) {
    $svc = aws ecs describe-services --cluster $cluster --services $service --region $Region | ConvertFrom-Json
    if (!$svc.services -or $svc.services.Count -eq 0) { Start-Sleep -Seconds 5; continue }
    $s = $svc.services[0]
    $running = [int]$s.runningCount
    $desired = [int]$s.desiredCount
    $primary = ($s.deployments | Where-Object { $_.status -eq "PRIMARY" })[0]
    if ($running -eq $desired -and $primary.rolloutState -eq "COMPLETED") { return }
    Start-Sleep -Seconds 6
  }
  throw "Timeout esperando a que el servicio $service esté estable"
}

function Set-ConcurrencyInContainer($containerDef, [int]$concurrency) {
  $cmd = @()
  if ($containerDef.command) { $cmd = @($containerDef.command) }
  $idx = $cmd.IndexOf("--concurrency")
  if ($idx -ge 0) {
    if ($idx -lt ($cmd.Count - 1)) { $cmd[$idx+1] = "$concurrency" } else { $cmd += "$concurrency" }
  } else {
    $cmd += @("--concurrency","$concurrency")
  }
  $containerDef.command = $cmd
  return $containerDef
}

function Update-WorkerConcurrency([int]$concurrency) {
  if ($SkipUpdateConcurrency) { Write-Host "  Saltando actualización de concurrencia (flag -SkipUpdateConcurrency)" -ForegroundColor DarkYellow; return }
  Write-Host "  Actualizando concurrencia del Worker a $concurrency ..." -ForegroundColor Cyan
  $svc = aws ecs describe-services --cluster $Cluster --services $ServiceWorker --region $Region | ConvertFrom-Json
  if (!$svc.services) { throw "Servicio ECS no encontrado: $ServiceWorker" }
  $currentTdArn = $svc.services[0].taskDefinition
  $td = aws ecs describe-task-definition --task-definition $currentTdArn --region $Region | ConvertFrom-Json
  $taskDef = $td.taskDefinition
  $containers = $taskDef.containerDefinitions
  for ($i=0; $i -lt $containers.Count; $i++) {
    if ($containers[$i].name -eq $WorkerContainer) {
      $containers[$i] = Set-ConcurrencyInContainer $containers[$i] $concurrency
    }
  }
  $newTd = [ordered]@{
    family = $taskDef.family
    taskRoleArn = $taskDef.taskRoleArn
    executionRoleArn = $taskDef.executionRoleArn
    networkMode = $taskDef.networkMode
    containerDefinitions = $containers
    volumes = $taskDef.volumes
    placementConstraints = $taskDef.placementConstraints
    requiresCompatibilities = $taskDef.requiresCompatibilities
    cpu = $taskDef.cpu
    memory = $taskDef.memory
    runtimePlatform = $taskDef.runtimePlatform
    ephemeralStorage = $taskDef.ephemeralStorage
  }
  $json = ($newTd | ConvertTo-Json -Depth 100)
  $reg = aws ecs register-task-definition --cli-input-json $json --region $Region | ConvertFrom-Json
  $newArn = $reg.taskDefinition.taskDefinitionArn
  aws ecs update-service --cluster $Cluster --service $ServiceWorker --task-definition $newArn --region $Region | Out-Null
  Wait-EcsServiceStable -cluster $Cluster -service $ServiceWorker
}

function Get-LatestWorkerLog {
  $files = Get-ChildItem -Path $ResultsDir -Filter 'worker_tasks_*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
  if (!$files -or $files.Count -eq 0) { throw "No se encontró worker_tasks_*.log en $ResultsDir" }
  return $files[0].FullName
}

function Compute-Metrics([string]$label) {
  $latestLog = Get-LatestWorkerLog
  $outCsv = Join-Path $ResultsDir ("metrics_{0}.csv" -f $label)
  Write-Host ("  Calculando métricas -> {0}" -f $outCsv) -ForegroundColor Cyan
  & python "load_tests/compute_worker_metrics.py" --tasks-log $latestLog --output-csv $outCsv
}

function Consolidate-Results {
  Write-Host " Consolidando CSVs" -ForegroundColor Cyan
  $cons = Join-Path $ResultsDir "scenario2_consolidated.csv"
  $rows = @()
  $files = Get-ChildItem -Path $ResultsDir -Filter 'metrics_*mb_c*_*.csv' -ErrorAction SilentlyContinue
  foreach ($f in $files) {
    $m = [regex]::Match($f.BaseName, 'metrics_(\d+)mb_c(\d+)_(burst|sustained)')
    if (!$m.Success) { continue }
    $size = [int]$m.Groups[1].Value
    $conc = [int]$m.Groups[2].Value
    $mode = $m.Groups[3].Value
    $data = Import-Csv $f.FullName
    foreach ($row in $data) {
      $rows += [pscustomobject]@{
        size_mb = $size
        concurrency = $conc
        mode = $mode
        total = $row.total
        done = $row.done
        failed = $row.failed
        processing = $row.processing
        uploaded = $row.uploaded
        throughput_videos_per_min = $row.throughput_videos_per_min
        service_avg_seconds = $row.service_avg_seconds
        service_p50_seconds = $row.service_p50_seconds
        start_ts = $row.start_ts
        end_ts = $row.end_ts
      }
    }
  }
  $rows | Export-Csv -NoTypeInformation -Path $cons
  Write-Host ("  CSV consolidado: {0}" -f $cons)
}

function Run-Test([int]$sizeMb, [int]$concurrency, [string]$mode, [int]$count, [int]$rate) {
  Write-Host ""
  Write-Host "========================================================================" -ForegroundColor DarkGray
  Write-Host ("  TEST: {0}MB  c{1}  mode={2}  count={3}  rate={4}/min" -f $sizeMb,$concurrency,$mode,$count,$rate)
  Write-Host "========================================================================" -ForegroundColor DarkGray
  Update-WorkerConcurrency -concurrency $concurrency
  $s3Uri = Ensure-S3Video -sizeMb $sizeMb
  $args = @("--count",$count,"--size","${sizeMb}MB","--file",$s3Uri,"--mode",$mode,"--monitor")
  if ($mode -eq "sustained" -and $rate -gt 0) { $args += @("--rate",$rate) }
  & python "load_tests/inject_worker_tasks.py" @args
  $label = ("{0}mb_c{1}_{2}" -f $sizeMb,$concurrency,$mode)
  Compute-Metrics -label $label
}

# --------------------- MAIN ---------------------
Preflight


$tests = @(
  @{ size=100; c=1; mode="sustained"; count=20; rate=5 },
  @{ size=50;  c=2; mode="burst";     count=40; rate=0 },
  @{ size=50;  c=2; mode="sustained"; count=50; rate=$SustainedRate50 },
  @{ size=100; c=2; mode="burst";     count=20; rate=0 },
  @{ size=100; c=2; mode="sustained"; count=30; rate=10 },
  @{ size=50;  c=4; mode="burst";     count=80; rate=0 },
  @{ size=50;  c=4; mode="sustained"; count=100; rate=$SustainedRate50 },
  @{ size=100; c=4; mode="burst";     count=40; rate=0 },
  @{ size=100; c=4; mode="sustained"; count=60; rate=$SustainedRate100 }
)

foreach ($t in $tests) {
  Run-Test -sizeMb $t.size -concurrency $t.c -mode $t.mode -count $t.count -rate $t.rate
}

Consolidate-Results

Write-Host ""
Write-Host '========================================================================'
Write-Host '  PRUEBAS COMPLETADAS (Windows)'
Write-Host '========================================================================'
Write-Host ("Resultados en: {0}" -f $ResultsDir)
Write-Host '  - CSVs individuales: metrics_*.csv'
Write-Host '  - CSV consolidado:   scenario2_consolidated.csv'
Write-Host ''



