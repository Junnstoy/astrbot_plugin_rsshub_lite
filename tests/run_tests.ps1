#!/usr/bin/env pwsh
<#
.SYNOPSIS
    RssHub lite Test Runner - PowerShell Version

.DESCRIPTION
    使用 PowerShell 运行 RssHub lite 插件测试。
    支持跨平台测试，使用 pytest。

.PARAMETER Verbose
    显示详细输出

.PARAMETER Quick
    快速模式（仅显示摘要）

.PARAMETER Category
    测试类别: unit, integration, all

.EXAMPLE
    .\run_tests.ps1
    # 运行所有测试

.EXAMPLE
    .\run_tests.ps1 -Verbose
    # 显示详细输出

.EXAMPLE
    .\run_tests.ps1 -Category unit
    # 仅运行单元测试

.EXAMPLE
    .\run_tests.ps1 -Quick
    # 快速模式
#>

param(
    [switch]$Verbose,
    [switch]$Quick,
    [ValidateSet("unit", "integration", "all")]
    [string]$Category = "all"
)

$ErrorActionPreference = "Stop"

# 获取脚本目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TestsDir = $ScriptDir
$PluginDir = Split-Path -Parent $TestsDir

# 检查 Python
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $PythonCmd) {
    Write-Error "Python not found. Please install Python 3.11 or later."
    exit 1
}

$PythonVersion = & $PythonCmd.Source --version 2>&1
Write-Host "Using: $PythonVersion" -ForegroundColor Cyan

# 构建参数
$Args = @()
if ($Verbose) {
    $Args += "-v"
}
if ($Quick) {
    $Args += "--quick"
}
if ($Category -ne "all") {
    $Args += "--category"
    $Args += $Category
}

# 运行测试
Write-Host ""
Write-Host "Running RssHub lite Tests..." -ForegroundColor Green
Write-Host "Category: $Category" -ForegroundColor Gray
Write-Host ""

$RunTestsPy = Join-Path $TestsDir "run_tests.py"

# 设置 Python 路径
$env:PYTHONPATH = "$PluginDir;$env:PYTHONPATH"

# 执行测试
& $PythonCmd.Source $RunTestsPy @Args

$ExitCode = $LASTEXITCODE

# 输出结果
Write-Host ""
if ($ExitCode -eq 0) {
    Write-Host "✓ All tests passed!" -ForegroundColor Green
} else {
    Write-Host "✗ Some tests failed!" -ForegroundColor Red
}

exit $ExitCode
