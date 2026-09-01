# Sealos 部署一键构建推送脚本 (PowerShell, Windows)
# 用法:
#   1. 在另一终端运行 `docker login` 登录 Docker Hub
#   2. 修改本脚本顶部的 $DockerHubUser 为你的 Docker Hub 用户名
#   3. 在项目根目录运行:
#        ./scripts/sealos_build_push.ps1
#   4. 脚本会:
#        - 用 docker buildx 构建 amd64 镜像(前端 + 后端)
#        - 推送到 Docker Hub
#        - 自动更新 .sealos/template/args.json 的 image tag
#
# 之后用以下命令部署到 Sealos:
#   node <SKILL_DIR>/scripts/deploy-template.mjs .sealos/template/index.yaml `
#       --args-file .sealos/template/args.json

param(
    # 修改为你的 Docker Hub 用户名(不含邮箱)
    [string]$DockerHubUser = 'your-dockerhub-username',

    # 镜像仓库(通常等于 username)
    [string]$FrontendRepo = 'ai-customer-frontend',
    [string]$BackendRepo = 'ai-customer-backend'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host '================================================' -ForegroundColor Cyan
Write-Host 'Sealos Deploy - Build & Push to Docker Hub' -ForegroundColor Cyan
Write-Host '================================================' -ForegroundColor Cyan
Write-Host "Docker Hub user: $DockerHubUser"
Write-Host "Project root:    $ProjectRoot"
Write-Host ''

# 1. 校验 Docker 是否可用 + 是否已登录
Write-Host '[1/5] Checking Docker...' -ForegroundColor Yellow
$dockerInfo = docker info 2>&1 | Out-String
if ($dockerInfo -notmatch 'Username:') {
    Write-Host "ERROR: Docker Hub 未登录。" -ForegroundColor Red
    Write-Host '请在另一个终端运行: docker login' -ForegroundColor Yellow
    Write-Host '然后输入你的 Docker Hub username + Access Token / password。' -ForegroundColor Yellow
    exit 1
}
Write-Host 'OK: Docker Hub 已登录' -ForegroundColor Green

# 2. 检查 buildx builder(多平台构建需要)
Write-Host '[2/5] Checking buildx builder...' -ForegroundColor Yellow
$buildxList = docker buildx ls 2>&1 | Out-String
if ($buildxList -notmatch 'default') {
    Write-Host 'Creating default buildx builder...' -ForegroundColor Yellow
    docker buildx create --name default --use --driver docker-container 2>&1 | Out-Null
}
docker buildx use default 2>&1 | Out-Null
Write-Host 'OK: buildx ready' -ForegroundColor Green

# 3. 生成 tag(YYYYMMDD-HHmmss,本地时区)
$tag = (Get-Date -Format 'yyyyMMdd-HHmmss')
$frontendImage = "$DockerHubUser/$FrontendRepo`:$tag"
$backendImage = "$DockerHubUser/$BackendRepo`:$tag"
Write-Host "Image tags:" -ForegroundColor Cyan
Write-Host "  Frontend: $frontendImage"
Write-Host "  Backend:  $backendImage"
Write-Host ''

# 4. 构建 + 推送后端
Write-Host "[3/5] Building & Pushing BACKEND image..." -ForegroundColor Yellow
$backendDir = Join-Path $ProjectRoot 'ai-customer-backend'
Push-Location $backendDir
docker buildx build `
    --platform linux/amd64 `
    --build-arg APP_VERSION=$tag `
    -t $backendImage `
    --push `
    -f Dockerfile .
$exitCode = $LASTEXITCODE
Pop-Location
if ($exitCode -ne 0) {
    Write-Host "ERROR: Backend build failed (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}
Write-Host "OK: backend image pushed: $backendImage" -ForegroundColor Green

# 5. 构建 + 推送前端
Write-Host "[4/5] Building & Pushing FRONTEND image..." -ForegroundColor Yellow
$frontendDir = Join-Path $ProjectRoot 'ai-customer-frontend'
Push-Location $frontendDir
docker buildx build `
    --platform linux/amd64 `
    --build-arg APP_VERSION=$tag `
    -t $frontendImage `
    --push `
    -f Dockerfile .
$exitCode = $LASTEXITCODE
Pop-Location
if ($exitCode -ne 0) {
    Write-Host "ERROR: Frontend build failed (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}
Write-Host "OK: frontend image pushed: $frontendImage" -ForegroundColor Green

# 6. 更新 args.json
Write-Host "[5/5] Updating .sealos/template/args.json..." -ForegroundColor Yellow
$argsPath = Join-Path $ProjectRoot '.sealos\template\args.json'
$argsDir = Split-Path -Parent $argsPath
if (-not (Test-Path $argsDir)) { New-Item -ItemType Directory -Force -Path $argsDir | Out-Null }

# 也更新 template.yaml 的 defaults 里的 image 引用
$templatePath = Join-Path $ProjectRoot '.sealos\template\index.yaml'
if (Test-Path $templatePath) {
    $template = Get-Content $templatePath -Raw
    $template = $template -replace 'your-dockerhub-username/ai-customer-frontend:latest', "$DockerHubUser/$FrontentRepo`:$tag"
    $template = $template -replace 'your-dockerhub-username/ai-customer-backend:latest', "$DockerHubUser/$BackendRepo`:$tag"
    Set-Content -Path $templatePath -Value $template -Encoding UTF8
    Write-Host "Updated template index.yaml with new image refs" -ForegroundColor Green
}

# 写入 args.json(部署时用 --args-file 引用)
$argsObj = [ordered]@{
    frontend_image_tag = $tag
    backend_image_tag = $tag
    mysql_host = ''           # 用户在 Sealos 控制台创建 MySQL 后填入
    mysql_port = '3306'
    mysql_user = 'root'
    mysql_password = ''       # 用户填入 MySQL 实例密码
    mysql_database = 'ai_customer'
    llm_api_key = ''          # 用户填入 duc.ai / OpenAI key
    embedding_api_key = ''   # 用户填入 DashScope / OpenAI key
    zhibo_api_token = ''     # 可选
}
$argsJson = $argsObj | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText($argsPath, $argsJson, [System.Text.UTF8Encoding]::new($false))
Write-Host "Wrote args.json: $argsPath" -ForegroundColor Green

Write-Host ''
Write-Host '================================================' -ForegroundColor Green
Write-Host 'BUILD & PUSH COMPLETE' -ForegroundColor Green
Write-Host '================================================' -ForegroundColor Green
Write-Host ''
Write-Host 'Next steps:' -ForegroundColor Cyan
Write-Host '1. Edit .sealos/template/args.json to fill in:' -ForegroundColor Cyan
Write-Host '   - mysql_host / mysql_password(在 Sealos 控制台创建 MySQL 后填入)'
Write-Host '   - llm_api_key / embedding_api_key'
Write-Host ''
Write-Host '2. Deploy to Sealos Cloud (北京):' -ForegroundColor Cyan
Write-Host '   $skillDir = "c:\Users\admin\.trae-cn\plugins\trae-remote-official\sealos\1.0.0\skills\sealos-deploy"'
Write-Host '   node "$skillDir\scripts\deploy-template.mjs" ".sealos/template/index.yaml" --args-file ".sealos/template/args.json"'
Write-Host ''
Write-Host '3. Or use Sealos web console -> 应用 -> 导入 YAML'
Write-Host '   (paste the contents of .sealos/template/index.yaml, fill args interactively)'