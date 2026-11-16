# Prints the methods, strings and fields referenced by a ComicRack CE method
# (and by compiler-generated lambdas whose name contains the method name).
param([string]$Assembly, [string]$Type, [string]$Method)
$cr = 'C:\Program Files\ComicRack Community Edition'
$asm = [Reflection.Assembly]::LoadFrom("$cr\$Assembly")
$t = $asm.GetType($Type, $true)
$flags = [Reflection.BindingFlags]'Public,NonPublic,Instance,Static,DeclaredOnly'
$targets = @($t.GetMethods($flags) | Where-Object { $_.Name -eq $Method })
foreach ($n in $t.GetNestedTypes([Reflection.BindingFlags]'Public,NonPublic')) {
    $targets += @($n.GetMethods($flags) | Where-Object { $_.Name -like "*$Method*" })
}
foreach ($m in $targets) {
    "== $($m.DeclaringType.Name).$($m.Name)"
    $body = $m.GetMethodBody()
    if (-not $body) { continue }
    $il = $body.GetILAsByteArray()
    $i = 0
    while ($i -lt $il.Length - 4) {
        $op = $il[$i]
        $tok = [BitConverter]::ToInt32($il, $i + 1)
        $hit = $null
        if ($op -eq 0x28 -or $op -eq 0x6F -or $op -eq 0x73) {
            try { $r = $m.Module.ResolveMethod($tok); $hit = "  $($r.DeclaringType.Name).$($r.Name)" } catch {}
        } elseif ($op -eq 0x72) {
            try { $hit = "  str '" + $m.Module.ResolveString($tok) + "'" } catch {}
        } elseif ($op -eq 0x7E -or $op -eq 0x7B -or $op -eq 0x7D -or $op -eq 0x80) {
            try { $f = $m.Module.ResolveField($tok); $hit = "  fld $($f.Name)" } catch {}
        }
        if ($hit) { $hit; $i += 5 } else { $i += 1 }
    }
}
