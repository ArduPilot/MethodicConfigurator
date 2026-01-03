# https://github.com/kislyuk/argcomplete/tree/main/contrib#powershell-support
#
# SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# To install, use "notepad $PROFILE" to open the PowerShell profile file, and add the following line to the end of the file:
#
# Import-Module C:\path\to\ardupilot_methodic_configurator_command_line_completion.psm1
#
# Then, restart the PowerShell terminal to make the changes take effect.

function Register-ScriptBlock {
    param(
        [Parameter(Mandatory=$true)]
        [string]$CommandName
    )

    $scriptBlock = [ScriptBlock]::Create(@"
        param(`$commandName, `$wordToComplete, `$cursorPosition)
        `$completion_file = New-TemporaryFile
        `$env:ARGCOMPLETE_USE_TEMPFILES = 1
        `$env:_ARGCOMPLETE_STDOUT_FILENAME = `$completion_file
        `$env:COMP_LINE = `$wordToComplete
        `$env:COMP_POINT = `$cursorPosition
        `$env:_ARGCOMPLETE = 1
        `$env:_ARGCOMPLETE_SUPPRESS_SPACE = 0
        `$env:_ARGCOMPLETE_IFS = "`n"
        `$env:_ARGCOMPLETE_SHELL = "powershell"

        $CommandName 2>&1 | Out-Null

        Get-Content `$completion_file | ForEach-Object {
            [System.Management.Automation.CompletionResult]::new(`$_, `$_, "ParameterValue", `$_)
        }
        Remove-Item `$completion_file, Env:\_ARGCOMPLETE_STDOUT_FILENAME, Env:\ARGCOMPLETE_USE_TEMPFILES, Env:\COMP_LINE, Env:\COMP_POINT, Env:\_ARGCOMPLETE, Env:\_ARGCOMPLETE_SUPPRESS_SPACE, Env:\_ARGCOMPLETE_IFS, Env:\_ARGCOMPLETE_SHELL
"@)

    Register-ArgumentCompleter -Native -CommandName $CommandName -ScriptBlock $scriptBlock
}

# Register all commands that need tab completion
$commands = @(
    'ardupilot_methodic_configurator',
    'extract_param_defaults',
    'annotate_params',
    'param_pid_adjustment_update',
    'mavftp'
)

foreach ($command in $commands) {
    Register-ScriptBlock -CommandName $command
}
