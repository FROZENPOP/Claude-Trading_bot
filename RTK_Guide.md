# Complete Guide to Using RTK - Rust Token Killer

## Overview

RTK (Rust Token Killer) is a token-optimized CLI proxy designed to reduce token consumption when using Claude Code by filtering and optimizing bash command output. It can cut up to 90% of bash output, significantly reducing the token usage of your Claude Code sessions.

## Installation Verification

Before using RTK, verify it's properly installed:

```bash
# Check version
rtk --version
# Should show: rtk X.Y.Z

# Test basic functionality
rtk gain
# Should work (not return "command not found")

# Verify correct binary location
which rtk
```

⚠️ **Important Name Collision Warning**: 
If `rtk gain` fails with "command not found" or unexpected behavior, you may have the wrong RTK installed (reachingforthejack/rtk - Rust Type Kit) instead of the intended Rust Token Killer. Ensure you have the correct version installed.

## Core Commands

RTK provides several meta-commands that must be used directly (not processed through the hook):

### 1. `rtk gain`
Shows token savings analytics and current usage statistics.

```bash
rtk gain
```

### 2. `rtk gain --history`
Displays command usage history with associated token savings.

```bash
rtk gain --history
```

### 3. `rtk discover`
Analyzes your Claude Code history to identify missed opportunities for token savings.

```bash
rtk discover
```

### 4. `rtk proxy <cmd>`
Executes a raw command without RTK filtering (useful for debugging when you need unfiltered output).

```bash
rtk proxy <command>
# Example: rtk proxy ls -la
```

## Hook-Based Usage (Transparent Operation)

The primary value of RTK comes from its automatic hook-based operation. Once properly configured, RTK transparently wraps your bash commands to optimize their output:

```
# When you type:
git status

# Claude Code's hook automatically transforms it to:
rtk git status

# This happens with 0 tokens overhead - the hook itself doesn't consume tokens
```

This transparent rewriting applies to:
- All standard bash commands (ls, cd, grep, find, etc.)
- Git commands (git status, git log, git diff, etc.)
- Development tools (npm, yarn, pip, cargo, etc.)
- Any other CLI tool you use in your workflow

## Benefits

1. **Significant Token Reduction**: Cuts bash output by up to 90%, allowing longer conversations without hitting token limits
2. **Zero Configuration**: Once installed and hooked, works automatically without changing your workflow
3. **Transparent Operation**: Commands behave exactly as expected; only the internal token consumption is reduced
4. **Debugging Capability**: Use `rtk proxy` when you need to see unfiltered output for troubleshooting

## Best Practices

1. **Always Trust the Hook**: Let Claude Code's hook automatically wrap your commands with `rtk` - don't manually prepend it unless debugging
2. **Use `rtk proxy` Sparingly**: Only use this when you specifically need to see unfiltered output (e.g., debugging command formatting issues)
3. **Monitor Savings**: Regularly check `rtk gain` and `rtk gain --history` to see your token savings
4. **Run `rtk discover` Periodically**: This helps identify patterns where you could further optimize your command usage
5. **Verify Installation**: Periodically run the installation verification steps to ensure RTK is working correctly

## Troubleshooting

### Problem: `rtk gain` returns "command not found"
- **Cause**: Wrong RTK package installed (Rust Type Kit instead of Rust Token Killer)
- **Solution**: Uninstall the incorrect package and install the proper Rust Token Killer version

### Problem: Commands seem slower than usual
- **Cause**: RTK is processing output (this is normal and expected)
- **Solution**: The slight processing overhead is outweighed by significant token savings

### Problem: Need to see exact command output for scripting
- **Solution**: Use `rtk proxy <your_command>` to bypass RTK filtering temporarily

## Integration with Claude Code Workflow

RTK is designed to work seamlessly with Claude Code:

1. **No Workflow Changes**: Continue typing commands exactly as you normally would
2. **Automatic Optimization**: The Claude Code hook handles the RTK wrapping transparently
3. **Extended Sessions**: With reduced token consumption, you can work longer without hitting context limits
4. **Better Resource Utilization**: More tokens available for actual code and less wasted on command output

## Example Workflow

Here's how a typical session might look with RTK active:

```bash
# User types (hook automatically adds rtk prefix):
git status
# Internally becomes: rtk git status → shows optimized git status output

# User types:
ls -la src/
# Internally becomes: rtk ls -la src/ → shows optimized directory listing

# When you need to see raw output for debugging:
rtk proxy git diff --stat
# Shows unfiltered git diff output

# Periodically check your savings:
rtk gain
# Displays your token savings statistics
```

## Conclusion

RTK (Rust Token Killer) provides a simple yet powerful way to reduce token consumption in Claude Code sessions by optimizing bash command output. By leveraging Claude Code's hook system, it operates transparently in the background, requiring no changes to your existing workflow while delivering significant token savings of up to 90%. Regular use of the meta-commands (`gain`, `gain --history`, `discover`) helps you monitor and maximize these savings over time.

Remember: The correct installation is crucial - verify you have the Rust Token Killer version, not the similarly named Rust Type Kit package.