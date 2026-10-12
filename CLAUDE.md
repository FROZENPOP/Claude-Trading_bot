\## Windows file path rules



This project runs on Windows. Claude Code's Edit and MultiEdit tools can encounter path handling and file state tracking issues when different path separator formats are used.



\* For Edit and MultiEdit, ALWAYS use Windows-style absolute paths with backslashes.



&#x20; \* Correct: `C:\\Users\\me\\project\\src\\app.ts`

&#x20; \* Avoid: `C:/Users/me/project/src/app.ts`

&#x20; \* Avoid: `/c/Users/me/project/src/app.ts`

\* Use the exact path format returned by Read, Glob, or Grep whenever possible.

\* Do not convert or normalize a path between tool calls.

\* Never mix slash styles within a single path.



This is a workaround for known Windows path handling issues in Claude Code. Forward-slash paths can sometimes work, but using consistent Windows-style paths with backslashes is more reliable for Edit and MultiEdit.



