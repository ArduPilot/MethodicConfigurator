# SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

# SPDX-License-Identifier: GPL-3.0-or-later

$scripts = @(
    'ardupilot_methodic_configurator',
    'extract_param_defaults',
    'annotate_params',
    'param_pid_adjustment_update',
    'mavftp'
)
foreach ($script in $scripts) {
    Register-ArgumentCompleter -Native -CommandName $script -ScriptBlock {
        param($wordToComplete, $commandAst, $cursorPosition)
        $command = $script
        $env:COMP_LINE = $commandAst.ToString()
        $env:COMP_POINT = $cursorPosition
        $env:_ARGCOMPLETE = "1"
        $env:_ARGCOMPLETE_COMP_WORDBREAKS = " `"`'><=;|&(:"
        $env:COMP_WORDS = $commandAst.ToString()
        $env:COMP_CWORD = $cursorPosition

        (& python -m argcomplete.completers $command) | ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }
    }
}
