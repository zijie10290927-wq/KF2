# API审查测试脚本 - 使用原始 curl.exe (避免 PowerShell Invoke-WebRequest 别名)
$ErrorActionPreference = "Continue"
$base = "http://localhost:8000/api/v1"
$curl = "curl.exe"
$script:token = $null
$script:sid = $null

function Write-Section($name, $body) {
    Write-Host ""
    Write-Host "=== $name ===" -ForegroundColor Cyan
    if ($body) { Write-Host $body }
}

# 1. health
Write-Section "1. /health"
& $curl -s http://localhost:8000/health
Write-Host ""

# 2. login
Write-Section "2. POST /auth/login (admin/admin123)"
$loginBody = '{"username":"admin","password":"admin123"}' | Out-File -FilePath api-test-temp.json -Encoding utf8
$loginRaw = & $curl -s -X POST "$base/auth/login" -H "Content-Type: application/json" -d "@api-test-temp.json"
$loginRaw
$loginObj = $loginRaw | ConvertFrom-Json -ErrorAction SilentlyContinue
if ($loginObj -and $loginObj.data -and $loginObj.data.access_token) {
    $script:token = $loginObj.data.access_token
    Write-Host ""
    Write-Host "Token OK: len=$($script:token.Length)" -ForegroundColor Green
    Write-Host "data keys: $($loginObj.data.PSObject.Properties.Name -join ', ')"
    Write-Host "Contains user_info field: $([bool]$loginObj.data.user_info)"
    Write-Host "Contains user field: $([bool]$loginObj.data.user)"
} else {
    Write-Host "LOGIN FAILED" -ForegroundColor Red
    exit 1
}

$authHeader = @("Authorization: Bearer $($script:token)")

# 3. /auth/me
Write-Section "3. GET /auth/me"
& $curl -s "$base/auth/me" -H $authHeader[0]
Write-Host ""

# 4. 创建会话
Write-Section "4. POST /chat/sessions"
'{"title":"审查测试会话"}' | Out-File sess.json -Encoding utf8
$sessRaw = & $curl -s -X POST "$base/chat/sessions" -H $authHeader[0] -H "Content-Type: application/json" -d "@sess.json"
$sessRaw
$sessObj = $sessRaw | ConvertFrom-Json -ErrorAction SilentlyContinue
if ($sessObj -and $sessObj.data -and $sessObj.data.session_id) {
    $script:sid = $sessObj.data.session_id
    Write-Host ""
    Write-Host "session_id = $($script:sid)" -ForegroundColor Green
}

# 5. 会话列表
Write-Section "5. GET /chat/sessions"
& $curl -s "$base/chat/sessions" -H $authHeader[0]
Write-Host ""

# 6. 消息历史
if ($script:sid) {
    Write-Section "6. GET /chat/sessions/$($script:sid)/messages"
    & $curl -s "$base/chat/sessions/$($script:sid)/messages" -H $authHeader[0]
    Write-Host ""
}

# 7. 转人工
Write-Section "7. POST /chat/transfer-human"
"{`"reason`":`"审查测试转人工`",`"session_id`":`"$($script:sid)`"}" | Out-File tf.json -Encoding utf8
& $curl -s -X POST "$base/chat/transfer-human" -H $authHeader[0] -H "Content-Type: application/json" -d "@tf.json"
Write-Host ""

# 8. 兜底配置
Write-Section "8. GET /admin/config/fallback"
& $curl -s "$base/admin/config/fallback" -H $authHeader[0]
Write-Host ""

# 9. 知识库文档 (若存在)
Write-Section "9. GET /knowledge/docs (if exists)"
& $curl -s "$base/knowledge/docs" -H $authHeader[0]
Write-Host ""

# 10. 模型配置
Write-Section "10. GET /admin/models (if exists)"
& $curl -s "$base/admin/models" -H $authHeader[0]
Write-Host ""

# 11. 管理用户列表
Write-Section "11. GET /admin/users (if exists)"
& $curl -s "$base/admin/users" -H $authHeader[0]
Write-Host ""

# 12. OpenAPI size
Write-Section "12. /openapi.json size"
& $curl -s http://localhost:8000/openapi.json -o oa-temp.json
Get-ChildItem oa-temp.json | Select-Object Length

# 13. 测试 401 /auth/me 无token
Write-Section "13. GET /auth/me WITHOUT token (expect 401/unauth)"
& $curl -s -w "HTTP_CODE:%{http_code}`n" "$base/auth/me"
Write-Host ""

# 14. 测试登录 - 错误密码
Write-Section "14. POST /auth/login wrong password (expect error)"
'{"username":"admin","password":"wrongpass"}' | Out-File wpass.json -Encoding utf8
& $curl -s -X POST "$base/auth/login" -H "Content-Type: application/json" -d "@wpass.json"
Write-Host ""

# 15. 会话 - 无token (401)
Write-Section "15. GET /chat/sessions WITHOUT token (expect 401/unauth)"
& $curl -s -w "HTTP_CODE:%{http_code}`n" "$base/chat/sessions"

# 保存信息到文件
$info = @{
    token = $script:token
    sid = $script:sid
}
$info | ConvertTo-Json | Out-File test-state.json -Encoding utf8

Write-Host ""
Write-Host "DONE. Token & session_id saved to test-state.json" -ForegroundColor Green
