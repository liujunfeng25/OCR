Set-Location $PSScriptRoot
python -m uvicorn main:app --host 0.0.0.0 --port 8010 $args
