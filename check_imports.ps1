# Checks every "from System... import Name" in src\*.py against the real
# .NET assemblies, so a wrong name fails here instead of inside ComicRack.
Add-Type -AssemblyName System.Windows.Forms, System.Drawing, System.Core, `
    System.Web.Extensions, System.Security
$asms = [AppDomain]::CurrentDomain.GetAssemblies()
function Exists($ns, $name) {
    # generic types are named Name`1, Name`2 ... (e.g. Dictionary`2)
    foreach ($candidate in @($name) + (1..4 | ForEach-Object { "$name``$_" })) {
        foreach ($a in $asms) {
            if ($a.GetType("$ns.$candidate", $false)) { return $true }
        }
    }
    return $false
}
$bad = 0
foreach ($f in Get-ChildItem "$PSScriptRoot\src\*.py") {
    $text = (Get-Content $f.FullName -Raw) -replace "\\\r?\n\s*", " "
    foreach ($m in [regex]::Matches($text, '(?m)^\s*from (System[\w\.]*) import ([^\r\n#]+)')) {
        $ns = $m.Groups[1].Value
        foreach ($n in $m.Groups[2].Value.Split(',')) {
            $name = ($n.Trim() -split '\s+as\s+')[0].Trim()
            if (-not $name) { continue }
            if (-not (Exists $ns $name)) {
                Write-Output "$($f.Name): $ns.$name NOT FOUND"
                $bad++
            }
        }
    }
}
Write-Output "missing: $bad"
