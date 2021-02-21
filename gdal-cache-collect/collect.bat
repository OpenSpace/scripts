@echo off

mkdir combined
for /r . %%G in (*) do (
    echo copy %%G combined\%%~nG.png
    echo f | xcopy /f /y %%G combined\%%~nG.png
)
