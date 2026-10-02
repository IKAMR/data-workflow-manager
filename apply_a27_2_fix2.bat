@echo off
setlocal
if exist "docs\A27-ARKADE-WORKFLOW-OPERATIONS.md" (
  del /q "docs\A27-ARKADE-WORKFLOW-OPERATIONS.md"
)
echo a27.2 fix2 applied.
endlocal
