$ErrorActionPreference = "Stop"

if (-not $env:HINDSIGHT_API_LLM_API_KEY) {
    Write-Error "HINDSIGHT_API_LLM_API_KEY is not set in this PowerShell session. Set your Groq API key first."
}

$env:HINDSIGHT_API_LLM_PROVIDER = "groq"
$env:HINDSIGHT_API_LLM_MODEL = "openai/gpt-oss-20b"
$env:HINDSIGHT_API_LLM_GROQ_SERVICE_TIER = "on_demand"
$env:HINDSIGHT_API_PORT = "8888"

Write-Host "Starting Hindsight on http://localhost:8888"
Write-Host "Provider: groq"
Write-Host "Model: openai/gpt-oss-20b"
Write-Host "Service tier: on_demand"

hindsight-api
