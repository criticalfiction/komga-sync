# Runs the static checks, then every tests\test_*.py in ComicRack CE's
# IronPython, then builds the plugin. Exit code 1 if anything failed.
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\run_tests.ps1 [name-filter]
param([string]$Filter = '')
Set-Location $PSScriptRoot
$failed = @()

$out = powershell -NoProfile -ExecutionPolicy Bypass -File .\check_imports.ps1
$out | Select-Object -Last 3
if (($out | Select-Object -Last 1) -ne 'missing: 0') { $failed += 'check_imports' }
python check_source.py
if ($LASTEXITCODE -ne 0) { $failed += 'check_source' }

foreach ($t in Get-ChildItem tests\test_*.py | Where-Object { $_.Name -like "*$Filter*" }) {
    "`n===== $($t.Name)"
    powershell -NoProfile -STA -ExecutionPolicy Bypass -File .\run_ironpython.ps1 $t.FullName
    if ($LASTEXITCODE -ne 0) { $failed += $t.Name }
}

"`n===== build"
python build.py
if ($LASTEXITCODE -ne 0) { $failed += 'build' }

if ($failed.Count) { "`nFAILED: $($failed -join ', ')"; exit 1 }
"`nALL PASSED"
