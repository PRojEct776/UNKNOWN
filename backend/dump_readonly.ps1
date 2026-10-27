function Show-Range($f, $a, $b) {
  "--- $f $a-$b"
  if (-not (Test-Path $f)) { "MISSING FILE"; return }
  $i = 0
  Get-Content $f | ForEach-Object {
    $i++
    if ($i -ge $a -and $i -le $b) { '{0}: {1}' -f $i, $_ }
  }
}

Show-Range 'app\rag\claim_verifier.py' 1 99999
Show-Range 'app\rag\research_gap_finder.py' 1 99999
Show-Range 'app\rag\debate_engine.py' 1 99999
Show-Range 'app\rag\knowledge_dna.py' 1 99999
Show-Range 'app\rag\knowledge_mind_map.py' 1 99999
Show-Range 'app\rag\research_comparison.py' 21 222
Show-Range 'app\rag\research_comparison.py' 432 99999
Show-Range 'app\reasoning\reasoning_engine.py' 354 99999
Show-Range 'app\main.py' 808 880
Show-Range 'app\main.py' 1091 1142
Show-Range 'app\main.py' 1360 1400

"--- RAG_SERVICE_ENTRYPOINTS"
Select-String -Path 'app\services\rag_service.py' -Pattern 'def verify','def reason','def compare','def find_research_gaps','def run_debate','def generate_knowledge_dna','def generate_knowledge_mind_map','def _retrieve' |
  ForEach-Object { '{0}: {1}' -f $_.LineNumber, $_.Line.Trim() }

"--- TESTS_IMPORTING_COMPARE_OR_GAPS"
Select-String -Path 'tests\*.py' -Pattern 'research_comparison','research_gap_finder','ResearchComparisonEngine','ResearchGapFinder' -List |
  ForEach-Object { $_.Path }

"--- API_TS_MOJIBAKE"
$b = [System.IO.File]::ReadAllBytes((Resolve-Path '..\frontend\src\lib\api.ts'))
$pat = [byte[]](0xC3,0xA2,0xE2,0x82,0xAC)
$found = $false
for ($k = 0; $k -le $b.Length - 5; $k++) {
  if ($b[$k] -eq $pat[0] -and $b[$k+1] -eq $pat[1] -and $b[$k+2] -eq $pat[2] -and $b[$k+3] -eq $pat[3] -and $b[$k+4] -eq $pat[4]) { $found = $true; break }
}
"mojibake bytes present: $found"