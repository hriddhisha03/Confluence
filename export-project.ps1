# ============================================
# Export Project Structure + File Contents
# ============================================

# CHANGE THIS to your project/folder path
$RootPath = "D:\mili\OutOfCollege\Data_Pipeline"
# Output file
$OutputFile = "$env:USERPROFILE\Desktop\project_dump.txt"

# Folders to skip
$ExcludedDirectories = @(
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "bin",
    "obj",
    "dist",
    "build",
    ".next",
    ".idea",
    ".vs"
)

# File extensions to include
$TextExtensions = @(
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".php",
    ".html", ".htm", ".css", ".scss",
    ".json", ".xml", ".yaml", ".yml",
    ".sql", ".md", ".txt",
    ".env.example",
    ".config", ".ini",
    ".properties",
    ".sh", ".ps1",
    ".bat", ".cmd"
)

# Start fresh
"PROJECT DUMP" | Out-File $OutputFile -Encoding UTF8
"Root: $RootPath" | Out-File $OutputFile -Append -Encoding UTF8
"Generated: $(Get-Date)" | Out-File $OutputFile -Append -Encoding UTF8
("=" * 100) | Out-File $OutputFile -Append -Encoding UTF8

# Get all files
$Files = Get-ChildItem -Path $RootPath -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        # Exclude unwanted directories
        $Path = $_.FullName

        $ShouldExclude = $false

        foreach ($Dir in $ExcludedDirectories) {
            if ($Path -match "[\\/]$([regex]::Escape($Dir))[\\/]") {
                $ShouldExclude = $true
                break
            }
        }

        # Only include text/code files
        $IsTextFile = $TextExtensions -contains $_.Extension.ToLower()

        (-not $ShouldExclude) -and $IsTextFile
    }

# Write files
foreach ($File in $Files) {

    $RelativePath = $File.FullName.Substring($RootPath.Length).TrimStart("\", "/")

    "`n" | Out-File $OutputFile -Append -Encoding UTF8
    ("=" * 100) | Out-File $OutputFile -Append -Encoding UTF8
    "FILE: $RelativePath" | Out-File $OutputFile -Append -Encoding UTF8
    "SIZE: $($File.Length) bytes" | Out-File $OutputFile -Append -Encoding UTF8
    ("=" * 100) | Out-File $OutputFile -Append -Encoding UTF8

    try {
        Get-Content $File.FullName -Raw -ErrorAction Stop |
            Out-File $OutputFile -Append -Encoding UTF8
    }
    catch {
        "[Could not read this file: $($_.Exception.Message)]" |
            Out-File $OutputFile -Append -Encoding UTF8
    }
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
Write-Host "Output file: $OutputFile"
Write-Host "Files included: $($Files.Count)"