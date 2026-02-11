$Env:CONDA_EXE = "C:\Anaconda3\Scripts\conda.exe"
$Env:_CE_M = ""
$Env:_CE_CONDA = ""
$Env:_CONDA_ROOT = "C:\Anaconda3"
$Env:_CONDA_EXE = "C:\Anaconda3\Scripts\conda.exe"
$CondaModuleArgs = @{ChangePs1 = $True}
Write-Host "Importing module..."
Import-Module "$Env:_CONDA_ROOT\shell\condabin\Conda.psm1" -ArgumentList $CondaModuleArgs
Write-Host "Activating base..."
conda activate base
Write-Host "Cleaning up..."
Remove-Variable CondaModuleArgs
Write-Host "Done."
