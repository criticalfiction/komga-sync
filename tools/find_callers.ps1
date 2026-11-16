# Lists methods in ComicRack CE assemblies whose IL calls a method with the
# given name (e.g. get_Configure). Used to learn how ComicRack wires hooks.
param([string]$Target = 'get_Configure')
$cr = 'C:\Program Files\ComicRack Community Edition'
$files = Get-ChildItem $cr -Filter *.dll | Where-Object { $_.Name -like 'ComicRack*' -or $_.Name -like 'cYo*' }
$files += Get-Item "$cr\ComicRack.exe"
foreach ($f in $files) {
    try { $asm = [Reflection.Assembly]::LoadFrom($f.FullName) } catch { continue }
    try { $types = $asm.GetTypes() } catch [Reflection.ReflectionTypeLoadException] { $types = $_.Exception.Types | Where-Object { $_ } }
    foreach ($t in $types) {
        $flags = [Reflection.BindingFlags]'Public,NonPublic,Instance,Static,DeclaredOnly'
        $methods = @($t.GetMethods($flags)) + @($t.GetConstructors($flags))
        foreach ($m in $methods) {
            try { $body = $m.GetMethodBody() } catch { continue }
            if (-not $body) { continue }
            $il = $body.GetILAsByteArray()
            for ($i = 0; $i -lt $il.Length - 4; $i++) {
                if ($il[$i] -eq 0x28 -or $il[$i] -eq 0x6F) {
                    $tok = [BitConverter]::ToInt32($il, $i + 1)
                    try { $r = $m.Module.ResolveMethod($tok) } catch { continue }
                    if ($r.Name -eq $Target) { "$($f.Name): $($t.FullName).$($m.Name)"; break }
                }
            }
        }
    }
}
