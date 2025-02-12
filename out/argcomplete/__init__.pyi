from . import completers as completers
from .completers import ChoicesCompleter as ChoicesCompleter, DirectoriesCompleter as DirectoriesCompleter, EnvironCompleter as EnvironCompleter, FilesCompleter as FilesCompleter, SuppressCompleter as SuppressCompleter
from .exceptions import ArgcompleteException as ArgcompleteException
from .finders import ExclusiveCompletionFinder as ExclusiveCompletionFinder, safe_actions as safe_actions
from .io import debug as debug, mute_stderr as mute_stderr, warn as warn
from .lexers import split_line as split_line
from .shell_integration import shellcode as shellcode
from _typeshed import Incomplete

autocomplete: Incomplete
