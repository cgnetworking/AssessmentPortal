<#
 .Synopsis
  Generates a formatted html report.

 .Description
    The generated html is a single file with the results of the assessment.

#>

function Get-HtmlReport {
    [CmdletBinding()]
    param(
        # The json of the results of the assessment.
        [Parameter(Mandatory = $true, Position = 0)]
        [psobject] $AssessmentResults,

        # Path to store temporary file used during generation
        [Parameter(Mandatory = $false)]
        [string] $Path
    )

    function ConvertTo-SafeInlineJson {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory = $true)]
            [string] $Json
        )

        # Keep the JSON valid while preventing values from ending the inline script tag.
        $safeJson = $Json.Replace('&', '\u0026')
        $safeJson = $safeJson.Replace('<', '\u003c')
        $safeJson = $safeJson.Replace('>', '\u003e')
        $safeJson = $safeJson.Replace([string][char]0x2028, '\u2028')
        $safeJson = $safeJson.Replace([string][char]0x2029, '\u2029')
        return $safeJson
    }

    #$json = $AssessmentResults | ConvertTo-Json -Depth 10 -WarningAction Ignore
    # Need to write to a file and read it back to avoid the json being escaped
    $resultsJsonPath = Join-Path $Path "ZeroTrustAssessmentReportTemp.json"
    $AssessmentResults | Out-File -FilePath $resultsJsonPath
    $json = Get-Content -Path $resultsJsonPath -Raw
    Remove-Item -Path $resultsJsonPath -Force -ErrorAction SilentlyContinue | Out-Null

    Write-PSFMessage -Message ('Assessment report JSON generated ({0} characters).' -f $json.Length) -Level Debug
    $htmlFilePath = Join-Path -Path $script:ModuleRoot -ChildPath 'assets/ReportTemplate.html'
    $templateHtml = Get-Content -Path $htmlFilePath -Raw

    # Insert the test results json into the template
    $startMarker = 'reportData={'
    $endMarker = 'EndOfJson:"EndOfJson"}'
    $insertLocationStart = $templateHtml.IndexOf($startMarker)
    $insertLocationEnd = $templateHtml.IndexOf($endMarker) + $endMarker.Length

    $outputHtml = $templateHtml.Substring(0, $insertLocationStart)
    $outputHtml += "reportData= $(ConvertTo-SafeInlineJson -Json $json)"
    $outputHtml += $templateHtml.Substring($insertLocationEnd)

    return $outputHtml
}
