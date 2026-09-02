# Sealos Deploy - Build and Push to Docker Hub (PowerShell)
# Usage:
#   docker login -u <your-dockerhub-user>
#   .\scripts\sealos_build_push.ps1

param(
    [string]$DockerHubUser = 'zijie1029',
    [string]$FrontendRepo = 'ai-customer-frontend',
    [string]$BackendRepo  = 'ai-customer-backend'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Sealos Deploy - Build and Push to Docker Hub"   -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Docker Hub user: $DockerHubUser"
Write-Host "Project root:    $ProjectRoot"
Write-Host ""

# === Step 1: Docker login check ===
Write-Host "[1/5] Checking Docker..." -ForegroundColor Yellow
$dockerInfo = docker info 2>&1 | Out-String
if ($dockerInfo -notmatch 'Username:') {
    Write-Host "ERROR: Docker Hub not logged in." -ForegroundColor Red
    Write-Host "Run: docker login -u $DockerHubUser" -ForegroundColor Yellow
    exit 1
}
Write-Host "OK: Docker Hub logged in" -ForegroundColor Green

# === Step 2: buildx ===
Write-Host "[2/5] Checking buildx builder..." -ForegroundColor Yellow
$buildxList = docker buildx ls 2>&1 | Out-String
if ($buildxList -notmatch 'default') {
    Write-Host "Creating default buildx builder..." -ForegroundColor Yellow
    docker buildx create --name default --use --driver docker-container 2>&1 | Out-Null
}
docker buildx use default 2>&1 | Out-Null
Write-Host "OK: buildx ready" -ForegroundColor Green

# === Step 3: tags ===
$tag = (Get-Date -Format 'yyyyMMdd-HHmmss')
$frontendImage = "$DockerHubUser/$FrontendRepo`:$tag"
$backendImage  = "$DockerHubUser/$BackendRepo`:$tag"
Write-Host "Image tags:" -ForegroundColor Cyan
Write-Host "  Frontend: $frontendImage"
Write-Host "  Backend:  $backendImage"
Write-Host ""

# === Step 4: Build and push backend ===
Write-Host "[3/5] Building and Pushing BACKEND image..." -ForegroundColor Yellow
$backendDir = Join-Path $ProjectRoot 'ai-customer-backend'
Push-Location $backendDir
$backendArgs = @(
    'buildx', 'build',
    '--platform', 'linux/amd64',
    '--build-arg', "APP_VERSION=$tag",
    '-t', $backendImage,
    '--push',
    '-f', 'Dockerfile',
    '.'
)
& docker @backendArgs
$exitCode = $LASTEXITCODE
Pop-Location
if ($exitCode -ne 0) {
    Write-Host "ERROR: Backend build failed (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}
Write-Host "OK: backend pushed: $backendImage" -ForegroundColor Green

# === Step 5: Build and push frontend ===
Write-Host "[4/5] Building and Pushing FRONTEND image..." -ForegroundColor Yellow
$frontendDir = Join-Path $ProjectRoot 'ai-customer-frontend'
Push-Location $frontendDir
$frontendArgs = @(
    'buildx', 'build',
    '--platform', 'linux/amd64',
    '--build-arg', "APP_VERSION=$tag",
    '-t', $frontendImage,
    '--push',
    '-f', 'Dockerfile',
    '.'
)
& docker @frontendArgs
$exitCode = $LASTEXITCODE
Pop-Location
if ($exitCode -ne 0) {
    Write-Host "ERROR: Frontend build failed (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}
Write-Host "OK: frontend pushed: $frontendImage" -ForegroundColor Green

# === Step 6: Write args.json ===
Write-Host "[5/5] Updating .sealos/template/args.json..." -ForegroundColor Yellow
$argsPath = Join-Path $ProjectRoot '.sealos\template\args.json'
$argsDir  = Split-Path -Parent $argsPath
if (-not (Test-Path $argsDir)) {
    New-Item -ItemType Directory -Force -Path $argsDir | Out-Null
}

# Also update template defaults (if still using placeholder username)
$templatePath = Join-Path $ProjectRoot '.sealos\template\index.yaml'
if (Test-Path $templatePath) {
    $template = Get-Content $templatePath -Raw
    $changed = $false
    if ($template -match 'your-dockerhub-username/') {
        $template = $template -replace 'your-dockerhub-username/ai-customer-frontend:latest', "$DockerHubUser/$FrontendRepo`:$tag"
        $template = $template -replace 'your-dockerhub-username/ai-customer-backend:latest',  "$DockerHubUser/$BackendRepo`:$tag"
        $changed = $true
    }
    if ($changed) {
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($templatePath, $template, $utf8NoBom)
        Write-Host "Updated template index.yaml with new image refs" -ForegroundColor Green
    }
}

$argsObj = [ordered]@{
    frontend_image_tag = $tag
    backend_image_tag  = $tag
    mysql_host         = ''
    mysql_port         = '3306'
    mysql_user         = 'root'
    mysql_password     = ''
    mysql_database     = 'ai_customer'
    llm_api_key        = ''
    embedding_api_key  = ''
    zhibo_api_token    = ''
}
$argsJson = $argsObj | ConvertTo-Json -Depth 5
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($argsPath, $argsJson, $utf8)
Write-Host "Wrote args.json: $argsPath" -ForegroundColor Green

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "BUILD AND PUSH COMPLETE"                        -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"                                              -ForegroundColor Cyan
Write-Host "1. Fill .sealos/template/args.json with secrets:"         -ForegroundColor Cyan
Write-Host "   - mysql_host / mysql_password (Sealos MySQL instance)"
Write-Host "   - llm_api_key / embedding_api_key"
Write-Host ""
Write-Host "2. Deploy via Sealos console -> App -> Import YAML"
Write-Host "   (paste .sealos/template/index.yaml, fill inputs)"
