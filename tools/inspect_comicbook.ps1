# Lists the read-state related members of ComicRack CE's ComicBook class and
# the plugin API (IApplication), so the plugin uses real names/types.
$cr = 'C:\Program Files\ComicRack Community Edition'
$engine = [Reflection.Assembly]::LoadFrom("$cr\ComicRack.Engine.dll")
$plugins = [Reflection.Assembly]::LoadFrom("$cr\ComicRack.Plugins.dll")

$book = $engine.GetType('cYo.Projects.ComicRack.Engine.ComicBook', $true)
"== ComicBook properties"
$book.GetProperties() | Where-Object {
    $_.Name -match 'Page|Read|Opened|FilePath|FileName|Id$|^Id|Modified|Added|Checked|Linked|Status|Count'
} | Sort-Object Name | ForEach-Object {
    '  {0,-26} {1,-14} CanWrite={2}' -f $_.Name, $_.PropertyType.Name, ($_.CanWrite -and $_.GetSetMethod() -ne $null)
}
"== ComicBook methods"
$book.GetMethods() | Where-Object { $_.DeclaringType -eq $book -and $_.Name -match 'Read|Page|Mark|Reset' } |
    Sort-Object Name | ForEach-Object {
        '  {0}({1}) -> {2}' -f $_.Name, (($_.GetParameters() | ForEach-Object { $_.ParameterType.Name + ' ' + $_.Name }) -join ', '), $_.ReturnType.Name
    } | Sort-Object -Unique
"== ComicBook events"
$book.GetEvents() | ForEach-Object { '  ' + $_.Name + ' : ' + $_.EventHandlerType.Name }

$app = $plugins.GetType('cYo.Projects.ComicRack.Plugins.Automation.IApplication', $true)
"== IApplication methods"
$app.GetMethods() | Sort-Object Name | ForEach-Object {
    '  {0}({1}) -> {2}' -f $_.Name, (($_.GetParameters() | ForEach-Object { $_.ParameterType.Name + ' ' + $_.Name }) -join ', '), $_.ReturnType.Name
}
